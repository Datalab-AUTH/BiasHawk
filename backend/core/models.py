import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction
from pgvector.django import HnswIndex, VectorField
from django.utils import timezone


# ---------------------------------------------------------------------------
# user
# ---------------------------------------------------------------------------


class UserManager(BaseUserManager):
    """Email is the login field; there is no separate username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    The only user table in the system.

    The old stack had two , a Prisma table in the frontend database and a shadow
    table in Django, reconciled by email on every request. This replaces both.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_short_name(self):
        return self.name or self.email.split("@")[0]

    def get_full_name(self):
        return self.name or self.email


# ---------------------------------------------------------------------------
# owner scoping
#
# Every domain queryset is filtered by owner at the manager, so a view cannot
# forget to do it. In the old backend 69 lookups resolved objects by UUID and
# only some filtered by user, which meant a UUID was enough to read anyone's
# analysis.
# ---------------------------------------------------------------------------


class UsecaseQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)


class InstanceQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(usecase__user=user)


class TimestampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# use cases
# ---------------------------------------------------------------------------


class Usecase(TimestampedModel):
    """An AI system being assessed."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="usecases")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Absorbed from the old MetadataUsecase table, which was a separate model
    # created 1:1 with every use case and whose `name` duplicated this one's.
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="System documentation extracted from uploaded files by the use case agent.",
    )

    objects = UsecaseQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


def usecase_file_path(instance, filename):
    return f"usecases/{instance.usecase_id}/files/{instance.id}/{filename}"


class UsecaseDataFile(TimestampedModel):
    """Documentation uploaded against a use case: PDF, Word, text or markdown."""

    DOCUMENT_MIME_TYPES = [
        ("application/pdf", "PDF"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "Word",
        ),
        ("text/plain", "Text"),
        ("text/markdown", "Markdown"),
    ]

    usecase = models.ForeignKey(Usecase, on_delete=models.CASCADE, related_name="data_files")
    file = models.FileField(upload_to=usecase_file_path, max_length=255)
    mime_type = models.CharField(
        max_length=100, choices=DOCUMENT_MIME_TYPES, default="text/plain"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.usecase.name} , {self.file.name}"


# ---------------------------------------------------------------------------
# instances
# ---------------------------------------------------------------------------


class Instance(TimestampedModel):
    """A specific dataset or version of a use case, and all analysis run on it."""

    usecase = models.ForeignKey(Usecase, on_delete=models.CASCADE, related_name="instances")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Absorbed from the old MetadataInstance table (see Usecase.metadata).
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Data compliance form extracted from uploaded files by the instance agent.",
    )

    # --- data governance ---
    data_profile_description = models.TextField(blank=True)

    # --- data quality ---
    data_quality_description = models.TextField(blank=True)
    data_quality_report = models.TextField(blank=True)
    quality_metrics = models.JSONField(default=dict, blank=True)
    quality_warnings = models.JSONField(default=dict, blank=True)

    # --- bias and fairness ---
    dataset_sensitive_features = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dataset column names mapped to their sensitive feature descriptions.",
    )
    analysis_results = models.JSONField(default=dict, blank=True)
    metrics_report = models.TextField(blank=True)
    warnings_report = models.TextField(blank=True)
    final_bias_report = models.TextField(blank=True)

    # --- NIST risk assessment ---
    nist_risk_report = models.TextField(blank=True)
    nist_risk_report_data = models.JSONField(default=dict, blank=True)

    objects = InstanceQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


def instance_file_path(instance, filename):
    return f"usecases/{instance.instance.usecase_id}/instances/{instance.instance_id}/files/{instance.id}/{filename}"


class InstanceDataFile(TimestampedModel):
    """Documentation uploaded against an instance."""

    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="data_files")
    file = models.FileField(upload_to=instance_file_path, max_length=255)
    mime_type = models.CharField(
        max_length=100,
        choices=UsecaseDataFile.DOCUMENT_MIME_TYPES,
        default="text/plain",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.instance.name} , {self.file.name}"


def dataset_file_path(instance, filename):
    return (
        f"usecases/{instance.instance.usecase_id}/instances/{instance.instance_id}"
        f"/datasets/{instance.kind}/{instance.id}/{filename}"
    )


class InstanceDatasetFile(TimestampedModel):
    """
    A CSV attached to an instance.

    The old schema had two models for this , InstanceDatasetFile and
    InstanceExportDatasetFile , that differed only in their upload path and
    otherwise duplicated the same 60 lines of CSV validation verbatim. `kind`
    replaces the second model.
    """

    SOURCE = "source"
    EXPORT = "export"
    KIND_CHOICES = [(SOURCE, "Source dataset"), (EXPORT, "Exported dataset")]

    instance = models.ForeignKey(
        Instance, on_delete=models.CASCADE, related_name="dataset_files"
    )
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default=SOURCE)
    file = models.FileField(upload_to=dataset_file_path, max_length=255)
    mime_type = models.CharField(max_length=100, default="text/csv")
    csv_features = models.JSONField(
        default=dict,
        blank=True,
        help_text="CSV column names mapped to their descriptions.",
    )
    csv_profile = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Shape of the CSV as uploaded: {'rows': int, 'distinct': {column: count}}. "
            "Lets a client tell which columns can be grouped on before anything is run."
        ),
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["instance", "kind"])]

    def __str__(self):
        return f"{self.instance.name} , {self.get_kind_display()}"


class InstanceDataDrift(TimestampedModel):
    """Drift between two instances of the same use case."""

    initial_instance = models.ForeignKey(
        Instance, on_delete=models.CASCADE, related_name="drift_as_initial"
    )
    comparison_instance = models.ForeignKey(
        Instance, on_delete=models.CASCADE, related_name="drift_as_comparison"
    )

    drift_detected = models.BooleanField(default=False)
    data_drift_summary = models.TextField(blank=True)
    data_drift_warnings = models.TextField(blank=True)
    # Both hold lists of per-feature findings, not mappings.
    data_drift_metrics = models.JSONField(default=list, blank=True)

    bias_drift_detected = models.BooleanField(default=False)
    bias_drift_events = models.JSONField(default=list, blank=True)
    bias_drift_summary = models.TextField(blank=True)

    final_drift_report = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["initial_instance", "comparison_instance"],
                name="unique_drift_pair",
            )
        ]

    def __str__(self):
        return f"Drift {self.initial_instance_id} → {self.comparison_instance_id}"


# ---------------------------------------------------------------------------
# jobs
#
# This table replaces RabbitMQ. The old stack already wrote a
# LongRunningTaskState row for every analysis and the frontend already polled
# it , the broker was carrying payloads between processes that all shared this
# database. Adding payload/attempts/error/locked_at turns that status table into
# the queue it was already half-being.
# ---------------------------------------------------------------------------


class JobQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)


class JobManager(models.Manager.from_queryset(JobQuerySet)):
    def claim(self):
        """
        Take ownership of one queued job, or return None.

        SELECT ... FOR UPDATE SKIP LOCKED is the whole reason no broker is
        needed: concurrent runner threads each get a different row and none of
        them block, with no coordination between them.
        """
        with transaction.atomic():
            job = (
                self.select_for_update(skip_locked=True)
                .filter(status=Job.QUEUED)
                .order_by("created_at")
                .first()
            )
            if job is None:
                return None
            job.status = Job.RUNNING
            job.attempts += 1
            job.locked_at = timezone.now()
            job.started_at = job.started_at or job.locked_at
            job.save(update_fields=["status", "attempts", "locked_at", "started_at", "updated_at"])
            return job

    def reclaim_stale(self):
        """
        Return jobs abandoned by a dead worker to the queue.

        Anything still marked running with a lock older than JOB_STALE_SECONDS
        had its process killed mid-flight. Retry it unless it has already used
        up its attempts.
        """
        cutoff = timezone.now() - timedelta(seconds=settings.JOB_STALE_SECONDS)
        stale = self.filter(status=Job.RUNNING, locked_at__lt=cutoff)

        exhausted = stale.filter(attempts__gte=settings.JOB_MAX_ATTEMPTS).update(
            status=Job.FAILED,
            error="Abandoned by a worker that stopped responding, and out of attempts.",
            locked_at=None,
            finished_at=timezone.now(),
        )
        requeued = stale.filter(attempts__lt=settings.JOB_MAX_ATTEMPTS).update(
            status=Job.QUEUED, locked_at=None
        )
        return requeued, exhausted


class Job(models.Model):
    QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
    STATUS_CHOICES = [
        (QUEUED, "Queued"),
        (RUNNING, "Running"),
        (DONE, "Done"),
        (FAILED, "Failed"),
    ]

    # Kinds match the handler keys in core.jobs.registry.
    KIND_CHOICES = [
        ("rag_ingest", "RAG ingestion"),
        ("usecase_extract", "Use case metadata extraction"),
        ("instance_extract", "Instance metadata extraction"),
        ("data_governance", "Data governance"),
        ("data_quality", "Data quality"),
        ("sensitive_features", "Sensitive feature detection"),
        ("bias_assessment", "Bias assessment"),
        ("bias_report", "Bias report"),
        ("drift", "Drift analysis"),
        ("risk_assessment", "NIST risk assessment"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=50, choices=KIND_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=QUEUED)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="jobs")
    usecase = models.ForeignKey(
        Usecase, on_delete=models.CASCADE, related_name="jobs", null=True, blank=True
    )
    instance = models.ForeignKey(
        Instance, on_delete=models.CASCADE, related_name="jobs", null=True, blank=True
    )

    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)

    attempts = models.PositiveSmallIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = JobManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # The claim query: filter on status, order by created_at.
            models.Index(fields=["status", "created_at"]),
            # The polling query: latest job for an instance and kind.
            models.Index(fields=["instance", "kind", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.kind} [{self.status}]"

    @property
    def is_terminal(self):
        return self.status in (self.DONE, self.FAILED)

    def mark_done(self, result=None):
        self.status = self.DONE
        self.result = result or {}
        self.error = ""
        self.locked_at = None
        self.finished_at = timezone.now()
        self.save(update_fields=["status", "result", "error", "locked_at", "finished_at", "updated_at"])

    def mark_failed(self, error):
        # Give the job back to the queue if it has attempts left; the runner
        # increments `attempts` on every claim.
        retryable = self.attempts < settings.JOB_MAX_ATTEMPTS
        self.status = self.QUEUED if retryable else self.FAILED
        self.error = str(error)[:20000]
        self.locked_at = None
        self.finished_at = None if retryable else timezone.now()
        self.save(update_fields=["status", "error", "locked_at", "finished_at", "updated_at"])
        return retryable


# ---------------------------------------------------------------------------
# RAG
#
# The old stack ran a second Postgres for this (rag_db, pgvector) reached by raw
# psycopg2 with its own RAG_DB_* credentials, plus a ChromaDB store for the NIST
# corpus. Both are now vector columns on the one application database.
# ---------------------------------------------------------------------------


class DocumentChunkQuerySet(models.QuerySet):
    def for_scope(self, *, usecase, instance=None):
        """
        Chunks visible to one retrieval scope.

        A use case sees only its own documents. An instance sees its own plus its
        use case's, which is what the old ingestion did implicitly by writing
        both sets of files under the instance's id.
        """
        queryset = self.filter(usecase=usecase)
        if instance is None:
            return queryset.filter(instance__isnull=True)
        return queryset.filter(models.Q(instance=instance) | models.Q(instance__isnull=True))


class DocumentChunk(models.Model):
    """One embedded passage of an uploaded document."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usecase = models.ForeignKey(Usecase, on_delete=models.CASCADE, related_name="chunks")
    instance = models.ForeignKey(
        Instance, on_delete=models.CASCADE, related_name="chunks", null=True, blank=True
    )

    document_name = models.CharField(max_length=1024)
    chunk_number = models.PositiveIntegerField(default=0)
    chunk_text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = DocumentChunkQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["usecase", "instance"]),
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_l2_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.document_name} #{self.chunk_number}"


class NistChunk(models.Model):
    """
    One embedded passage of the NIST AI RMF corpus.

    The old risk-assessment service kept this in a ChromaDB store on its own
    volume, re-ingesting on every workflow construction. It is a static public
    document, so it belongs here, embedded once, alongside every other vector.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_name = models.CharField(max_length=255)
    page = models.PositiveIntegerField(default=0)
    chunk_number = models.PositiveIntegerField(default=0)
    chunk_text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIM)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            HnswIndex(
                name="nist_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_l2_ops"],
            ),
        ]

    def __str__(self):
        return f"{self.document_name} p{self.page} #{self.chunk_number}"


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------


class ErrorLog(models.Model):
    """Failures surfaced from job handlers, kept for support."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    origin = models.CharField(max_length=255, help_text="Job kind or subsystem that failed.")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.origin} @ {self.created_at:%Y-%m-%d %H:%M}"
