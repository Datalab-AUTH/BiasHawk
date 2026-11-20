import logging

import pandas as pd
from rest_framework import serializers

from core.models import (
    Instance,
    InstanceDataDrift,
    InstanceDataFile,
    InstanceDatasetFile,
    Job,
    Usecase,
    UsecaseDataFile,
    User,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name", "date_joined"]
        read_only_fields = fields


class FileSerializer(serializers.ModelSerializer):
    filename = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()

    class Meta:
        model = UsecaseDataFile
        fields = ["id", "filename", "mime_type", "size", "created_at"]
        read_only_fields = fields

    def get_filename(self, obj):
        return obj.file.name.rsplit("/", 1)[-1] if obj.file else ""

    def get_size(self, obj):
        try:
            return obj.file.size
        except (OSError, ValueError):
            return None


DOCUMENT_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown"}
MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


class DocumentUploadMixin(serializers.Serializer):
    """Shared validation for the document types the RAG loaders can read."""

    file = serializers.FileField(write_only=True)

    def validate_file(self, value):
        suffix = "." + value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
        if suffix not in DOCUMENT_SUFFIXES:
            raise serializers.ValidationError(
                f"{value.name}: unsupported document type. "
                f"Supported: {', '.join(sorted(DOCUMENT_SUFFIXES))}"
            )
        self._suffix = suffix
        return value

    def create(self, validated_data):
        validated_data.setdefault("mime_type", MIME_BY_SUFFIX[self._suffix])
        return super().create(validated_data)


class UsecaseDataFileSerializer(DocumentUploadMixin, FileSerializer):
    class Meta(FileSerializer.Meta):
        model = UsecaseDataFile
        fields = FileSerializer.Meta.fields + ["file"]
        read_only_fields = ["id", "filename", "mime_type", "size", "created_at"]


class InstanceDataFileSerializer(DocumentUploadMixin, FileSerializer):
    class Meta(FileSerializer.Meta):
        model = InstanceDataFile
        fields = FileSerializer.Meta.fields + ["file"]
        read_only_fields = ["id", "filename", "mime_type", "size", "created_at"]


log = logging.getLogger("core.serializers")


def _csv_profile(frame):
    """
    What a client needs to know about the shape of a CSV before running anything.

    `distinct` is the count of distinct values per column: a sensitive feature
    is compared by grouping on those, so a column with one value per row cannot
    be compared at all. See MAX_GROUP_VALUES in core.analysis.bias.
    """
    return {
        "rows": int(len(frame)),
        "distinct": {
            str(column): int(frame[column].nunique(dropna=True)) for column in frame.columns
        },
    }


class InstanceDatasetFileSerializer(FileSerializer):
    file = serializers.FileField(write_only=True)

    class Meta(FileSerializer.Meta):
        model = InstanceDatasetFile
        fields = FileSerializer.Meta.fields + ["kind", "csv_features", "csv_profile", "file"]
        read_only_fields = [
            "id",
            "filename",
            "mime_type",
            "size",
            "created_at",
            "csv_features",
            "csv_profile",
        ]

    def validate_file(self, value):
        """
        Confirm it parses as CSV, and measure it.

        The old models did this in save(), which meant a malformed upload raised
        a ValidationError from inside the ORM and surfaced as a 500.

        The whole frame is read rather than just the header: the distinct count
        per column is what tells a client whether a column can be grouped on,
        and every analysis reads the file in full anyway.
        """
        try:
            value.seek(0)
            frame = pd.read_csv(value)
        except Exception as exc:
            raise serializers.ValidationError(f"Not a readable CSV file: {exc}") from exc
        finally:
            value.seek(0)

        columns = [str(column) for column in frame.columns]
        if not columns:
            raise serializers.ValidationError("The CSV has no columns.")
        self._columns = columns
        self._profile = _csv_profile(frame)
        return value

    def create(self, validated_data):
        validated_data.setdefault("mime_type", "text/csv")
        validated_data["csv_features"] = {column: "" for column in getattr(self, "_columns", [])}
        validated_data["csv_profile"] = getattr(self, "_profile", {})
        return super().create(validated_data)

    def to_representation(self, instance):
        """
        Fill in the profile for a dataset uploaded before it was measured.

        Reading the file once and keeping the answer beats asking every client
        to guess, and beats a data migration that has to reach into media.
        """
        if not instance.csv_profile:
            try:
                with instance.file.open("rb") as handle:
                    instance.csv_profile = _csv_profile(pd.read_csv(handle))
                instance.save(update_fields=["csv_profile", "updated_at"])
            except Exception:
                log.warning("Could not profile dataset %s.", instance.pk, exc_info=True)
        return super().to_representation(instance)


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "id",
            "kind",
            "status",
            "usecase",
            "instance",
            "attempts",
            "error",
            "result",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class UsecaseSerializer(serializers.ModelSerializer):
    instance_count = serializers.IntegerField(source="instances.count", read_only=True)

    class Meta:
        model = Usecase
        fields = [
            "id",
            "name",
            "description",
            "metadata",
            "instance_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "instance_count", "created_at", "updated_at"]


class InstanceSerializer(serializers.ModelSerializer):
    usecase = serializers.PrimaryKeyRelatedField(queryset=Usecase.objects.none())
    has_dataset = serializers.SerializerMethodField()

    class Meta:
        model = Instance
        fields = [
            "id",
            "usecase",
            "name",
            "description",
            "metadata",
            "dataset_sensitive_features",
            "has_dataset",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_has_dataset(self, instance) -> bool:
        """
        Is there a CSV to analyse?

        Every analysis reads the source dataset, so the client needs to know
        whether one exists before it offers to run anything , without it the
        job is enqueued only to fail in the worker.
        """
        return instance.dataset_files.filter(
            kind=InstanceDatasetFile.SOURCE
        ).exists()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Scope the writable FK to the caller's own use cases, so an instance
        # cannot be attached to somebody else's by passing their UUID.
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["usecase"].queryset = Usecase.objects.for_user(request.user)


class InstanceDetailSerializer(InstanceSerializer):
    """Adds the analysis result payloads, which the list view omits."""

    class Meta(InstanceSerializer.Meta):
        fields = InstanceSerializer.Meta.fields + [
            "data_profile_description",
            "data_quality_description",
            "data_quality_report",
            "quality_metrics",
            "quality_warnings",
            "analysis_results",
            "metrics_report",
            "warnings_report",
            "final_bias_report",
            "nist_risk_report",
            "nist_risk_report_data",
        ]


class DriftRecordSerializer(serializers.ModelSerializer):
    initial_instance_name = serializers.CharField(source="initial_instance.name", read_only=True)
    comparison_instance_name = serializers.CharField(
        source="comparison_instance.name", read_only=True
    )

    class Meta:
        model = InstanceDataDrift
        fields = [
            "id",
            "initial_instance",
            "initial_instance_name",
            "comparison_instance",
            "comparison_instance_name",
            "drift_detected",
            "data_drift_summary",
            "data_drift_warnings",
            "data_drift_metrics",
            "bias_drift_detected",
            "bias_drift_events",
            "bias_drift_summary",
            "final_drift_report",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
