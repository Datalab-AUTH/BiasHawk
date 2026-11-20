"""
The job runner , what replaced RabbitMQ and its nine consumer containers.

Each thread runs its own claim loop against Postgres. `SELECT ... FOR UPDATE
SKIP LOCKED` hands every thread a different row and never blocks, so the threads
need no coordination with each other and no broker between them.
"""

import logging
import signal
import threading
import time
import traceback

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection

from core.jobs.registry import get_handler, known_kinds
from core.models import ErrorLog, Job

log = logging.getLogger("core.jobs")


class Command(BaseCommand):
    help = "Claim and run queued jobs until stopped."

    def add_arguments(self, parser):
        parser.add_argument(
            "--threads",
            type=int,
            default=settings.JOB_THREADS,
            help=f"Worker threads (default {settings.JOB_THREADS}, from JOB_THREADS).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Drain the queue and exit, instead of polling forever. For tests.",
        )

    def handle(self, *args, **options):
        thread_count = max(1, options["threads"])
        run_once = options["once"]
        stop = threading.Event()

        if not run_once:
            self._install_signal_handlers(stop)

        log.info(
            "Job runner starting: %d threads, %ds poll, kinds=%s",
            thread_count, settings.JOB_POLL_SECONDS, ", ".join(known_kinds()) or "none",
        )

        self._reclaim_stale()

        if run_once:
            processed = 0
            while self._run_one():
                processed += 1
            log.info("Drained %d job(s).", processed)
            return

        threads = [
            threading.Thread(target=self._loop, args=(i, stop), name=f"job-{i}", daemon=True)
            for i in range(thread_count)
        ]
        for thread in threads:
            thread.start()

        # The main thread also sweeps for jobs abandoned by a killed worker.
        try:
            last_sweep = time.monotonic()
            while not stop.is_set():
                stop.wait(1)
                if time.monotonic() - last_sweep >= 60:
                    self._reclaim_stale()
                    last_sweep = time.monotonic()
        except KeyboardInterrupt:
            stop.set()

        for thread in threads:
            thread.join(timeout=30)
        log.info("Job runner stopped.")

    # -- internals ---------------------------------------------------------

    def _install_signal_handlers(self, stop):
        def request_stop(signum, _frame):
            log.info("Signal %s received , finishing current jobs and stopping.", signum)
            stop.set()

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)

    def _reclaim_stale(self):
        try:
            requeued, failed = Job.objects.reclaim_stale()
            if requeued or failed:
                log.warning("Reclaimed stale jobs: %d requeued, %d failed.", requeued, failed)
        except Exception:
            log.exception("Stale job sweep failed.")
        finally:
            close_old_connections()

    def _loop(self, index, stop):
        while not stop.is_set():
            try:
                worked = self._run_one()
            except Exception:
                log.exception("Unhandled error in job thread %d", index)
                worked = False
            if not worked:
                stop.wait(settings.JOB_POLL_SECONDS)

    def _run_one(self):
        """Claim and run a single job. Returns True if one was processed."""
        job = None
        try:
            job = Job.objects.claim()
            if job is None:
                return False

            log.info("Running job %s (%s), attempt %d", job.id, job.kind, job.attempts)
            started = time.monotonic()
            handler = get_handler(job.kind)
            result = handler(job) or {}
            job.mark_done(result)
            log.info("Job %s done in %.1fs: %s", job.id, time.monotonic() - started, result)

        except Exception as exc:
            if job is None:
                raise
            detail = traceback.format_exc()
            retrying = job.mark_failed(detail)
            log.error(
                "Job %s (%s) failed on attempt %d%s: %s",
                job.id, job.kind, job.attempts,
                " , requeued" if retrying else " , giving up", exc,
            )
            if not retrying:
                try:
                    ErrorLog.objects.create(origin=job.kind, message=detail)
                except Exception:
                    log.exception("Could not record ErrorLog for job %s", job.id)
        finally:
            # Connections are thread-local; without this each runner thread
            # holds one open indefinitely.
            connection.close()

        return True
