"use client";

import { AlertCircle, CheckCircle2, Clock, Play, TriangleAlert } from "lucide-react";

import { JOB_LABELS } from "@/lib/jobs";
import type { Job, JobKind } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/primitives";

export function JobBadge({ job }: { job: Job | undefined }) {
  if (!job) return <Badge tone="neutral">Not run</Badge>;

  switch (job.status) {
    case "queued":
      return (
        <Badge tone="info">
          <Clock className="size-3" aria-hidden /> Queued
        </Badge>
      );
    case "running":
      return (
        <Badge tone="info">
          <Spinner className="size-3" /> Running
        </Badge>
      );
    case "done":
      return (
        <Badge tone="success">
          <CheckCircle2 className="size-3" aria-hidden /> Done
        </Badge>
      );
    case "failed":
      return (
        <Badge tone="danger">
          <AlertCircle className="size-3" aria-hidden /> Failed
        </Badge>
      );
  }
}

/**
 * One analysis: what it is, whether it has run, and a button to run it.
 *
 * A failed job shows its reason rather than only a red badge , the runner
 * stores the traceback and the last line is usually the actionable part.
 */
export function AnalysisRow({
  kind,
  job,
  description,
  disabled,
  disabledReason,
  onRun,
  running,
  children,
}: {
  kind: JobKind;
  job: Job | undefined;
  description?: string;
  disabled?: boolean;
  disabledReason?: string;
  onRun: () => void;
  running?: boolean;
  children?: React.ReactNode;
}) {
  const active = job?.status === "queued" || job?.status === "running";
  const failureReason = job?.status === "failed" ? lastMeaningfulLine(job.error) : null;

  return (
    <div className="flex flex-col gap-3 border-b border-border py-4 last:border-b-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-medium">{JOB_LABELS[kind]}</span>
            <JobBadge job={job} />
          </div>
          {description ? (
            <p className="text-sm text-muted-foreground text-balance">{description}</p>
          ) : null}
          {disabled && disabledReason ? (
            <p className="flex items-center gap-1.5 rounded-md bg-amber-500/10 px-2 py-1 text-xs text-amber-600">
              <TriangleAlert className="size-3.5 shrink-0" aria-hidden />
              {disabledReason}
            </p>
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          {children}
          <Button
            size="sm"
            variant={job?.status === "done" ? "outline" : "default"}
            onClick={onRun}
            loading={running}
            disabled={disabled || active}
          >
            {!running && <Play />}
            {job?.status === "done" ? "Re-run" : "Run"}
          </Button>
        </div>
      </div>

      {failureReason ? (
        <p className="rounded-md bg-destructive/10 px-3 py-2 font-mono text-xs text-destructive">
          {failureReason}
        </p>
      ) : null}
    </div>
  );
}

/** The exception line from a Python traceback, which is the part worth showing. */
function lastMeaningfulLine(error: string) {
  const lines = error.trim().split("\n").filter(Boolean);
  return lines.length ? lines[lines.length - 1].slice(0, 300) : "The job failed.";
}

/**
 * Read-only progress for the upload pipeline.
 *
 * Ingestion and extraction run automatically when a document is uploaded, so
 * there is nothing to press here , only the current state to report.
 */
export function PipelineStatus({
  ingest,
  extract,
}: {
  ingest: Job | undefined;
  extract: Job | undefined;
}) {
  const active = (job: Job | undefined) =>
    job?.status === "queued" || job?.status === "running";

  if (extract?.status === "done") {
    return (
      <Badge tone="success">
        <CheckCircle2 className="size-3" aria-hidden /> Up to date
      </Badge>
    );
  }
  if (extract?.status === "failed" || ingest?.status === "failed") {
    return (
      <Badge tone="danger">
        <AlertCircle className="size-3" aria-hidden /> Could not read the documents
      </Badge>
    );
  }
  if (active(extract)) {
    return (
      <Badge tone="info">
        <Spinner className="size-3" /> Reading the documents
      </Badge>
    );
  }
  if (active(ingest)) {
    return (
      <Badge tone="info">
        <Spinner className="size-3" /> Indexing
      </Badge>
    );
  }
  return null;
}
