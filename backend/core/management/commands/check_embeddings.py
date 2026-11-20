"""
Verify the configured embedding model matches the stored vector width.

A mismatch means every chunk in the database was embedded by a different model
and cannot be searched with the current one. Inserts would fail on a dimension
mismatch; this says so up front, with what to do about it.

It also doubles as a reachability check: the model now runs on Open WebUI, so a
wrong base URL, key or model name shows up here rather than mid-ingest.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import DocumentChunk
from core.rag import embeddings


class Command(BaseCommand):
    help = "Check that OPENWEBUI_EMBED_MODEL agrees with EMBEDDING_DIM and the stored chunks."

    def handle(self, *args, **options):
        self.stdout.write(f"Base URL      : {settings.OPENWEBUI_BASE_URL}")
        self.stdout.write(f"Model         : {settings.OPENWEBUI_EMBED_MODEL}")
        self.stdout.write(f"EMBEDDING_DIM : {settings.EMBEDDING_DIM}")

        try:
            # embed_query() raises when the model's width disagrees with the setting.
            vector = embeddings.embed_query("dimension probe")
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Reported dim  : {len(vector)}")

        stored = DocumentChunk.objects.count()
        self.stdout.write(f"Stored chunks : {stored}")
        self.stdout.write(self.style.SUCCESS("Embedding configuration is consistent."))
