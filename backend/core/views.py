from django.db import connection
from django.http import FileResponse, Http404, HttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.jobs import enqueue
from core.jobs.registry import get_handler
from core.models import (
    DocumentChunk,
    Instance,
    InstanceDataDrift,
    InstanceDataFile,
    InstanceDatasetFile,
    Job,
    Usecase,
    UsecaseDataFile,
)
from core.analysis.bias_explanations import BIAS_METRICS
from core.analysis.bias_explanations import explain as explain_bias_metric
from core.rag import query as rag_query
from core.reports import DRIFT_REPORTS, INSTANCE_REPORTS, render_pdf
from core.serializers import (
    DriftRecordSerializer,
    InstanceDatasetFileSerializer,
    InstanceDataFileSerializer,
    InstanceDetailSerializer,
    InstanceSerializer,
    FileSerializer,
    JobSerializer,
    UsecaseDataFileSerializer,
    UsecaseSerializer,
    UserSerializer,
)


# ---------------------------------------------------------------------------
# infrastructure
# ---------------------------------------------------------------------------


class HealthView(APIView):
    """
    Liveness probe for compose healthchecks and the load balancer.

    Opted out of the global IsAuthenticated default: orchestration probes this
    before any user exists, and it discloses nothing beyond whether the process
    can reach its database.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            database_ok = True
        except Exception:
            database_ok = False

        return Response(
            {"status": "ok" if database_ok else "degraded", "database": database_ok},
            status=200 if database_ok else 503,
        )


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """
    Hands the frontend a CSRF token and sets the cookie.

    Opted out of IsAuthenticated: the sign-in form needs the token before any
    session exists. The token is not a secret , it is only useful to a caller
    that can also read the paired cookie.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class MeView(APIView):
    """The signed-in user, or 403 from the global default if there isn't one."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)


# ---------------------------------------------------------------------------
# use cases
#
# Every queryset below goes through `.for_user(request.user)`. An object that
# belongs to somebody else is not "forbidden", it is absent , the lookup simply
# does not find it and DRF returns 404, which also avoids confirming that the
# UUID exists at all.
# ---------------------------------------------------------------------------


class UsecaseListView(generics.ListCreateAPIView):
    serializer_class = UsecaseSerializer

    def get_queryset(self):
        return Usecase.objects.for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UsecaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UsecaseSerializer

    def get_queryset(self):
        return Usecase.objects.for_user(self.request.user)


class UsecaseFileListView(generics.ListCreateAPIView):
    """Documentation attached to a use case. Feeds rag_ingest."""

    serializer_class = UsecaseDataFileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_usecase(self):
        return get_object_or_404(
            Usecase.objects.for_user(self.request.user), pk=self.kwargs["usecase_id"]
        )

    def get_queryset(self):
        return self.get_usecase().data_files.all()

    def perform_create(self, serializer):
        usecase = self.get_usecase()
        serializer.save(usecase=usecase)
        # Uploading documentation is a request to have it read; start that now.
        enqueue("rag_ingest", user=self.request.user, usecase=usecase)


# ---------------------------------------------------------------------------
# instances
# ---------------------------------------------------------------------------


class InstanceListView(generics.ListCreateAPIView):
    serializer_class = InstanceSerializer

    def get_queryset(self):
        queryset = Instance.objects.for_user(self.request.user)
        usecase_id = self.request.query_params.get("usecase")
        if usecase_id:
            queryset = queryset.filter(usecase_id=usecase_id)
        return queryset


class InstanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = InstanceDetailSerializer

    def get_queryset(self):
        return Instance.objects.for_user(self.request.user)


class InstanceFileListView(generics.ListCreateAPIView):
    """Documentation attached to an instance. Feeds rag_ingest."""

    serializer_class = InstanceDataFileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_instance(self):
        return get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )

    def get_queryset(self):
        return self.get_instance().data_files.all()

    def perform_create(self, serializer):
        instance = self.get_instance()
        serializer.save(instance=instance)
        enqueue("rag_ingest", user=self.request.user, instance=instance)


class InstanceDatasetListView(generics.ListCreateAPIView):
    serializer_class = InstanceDatasetFileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_instance(self):
        return get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )

    def get_queryset(self):
        return self.get_instance().dataset_files.all()

    def perform_create(self, serializer):
        serializer.save(instance=self.get_instance())


# ---------------------------------------------------------------------------
# jobs
#
# Enqueueing returns 202 and a job id. Nothing is computed in the request ,
# the runner picks the row up out of Postgres. The client polls the job.
# ---------------------------------------------------------------------------


class InstanceJobListView(generics.ListAPIView):
    """Jobs for one instance, newest first. `?kind=` narrows to one analysis."""

    serializer_class = JobSerializer

    def get_queryset(self):
        instance = get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )
        queryset = instance.jobs.all()
        kind = self.request.query_params.get("kind")
        return queryset.filter(kind=kind) if kind else queryset

    def post(self, request, instance_id):
        instance = get_object_or_404(
            Instance.objects.for_user(request.user), pk=instance_id
        )
        kind = (request.data.get("kind") or "").strip()

        valid_kinds = {choice for choice, _ in Job.KIND_CHOICES}
        if kind not in valid_kinds:
            return Response(
                {"kind": [f"Unknown job kind {kind!r}."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            get_handler(kind)
        except LookupError as exc:
            return Response({"kind": [str(exc)]}, status=status.HTTP_501_NOT_IMPLEMENTED)

        job, created = enqueue(
            kind,
            user=request.user,
            instance=instance,
            payload=request.data.get("payload") or {},
        )
        return Response(
            JobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )


class UsecaseJobListView(generics.ListAPIView):
    """
    Jobs scoped to a use case rather than an instance , currently rag_ingest of
    the use case's own documents.
    """

    serializer_class = JobSerializer

    def get_queryset(self):
        usecase = get_object_or_404(
            Usecase.objects.for_user(self.request.user), pk=self.kwargs["usecase_id"]
        )
        queryset = usecase.jobs.filter(instance__isnull=True)
        kind = self.request.query_params.get("kind")
        return queryset.filter(kind=kind) if kind else queryset

    def post(self, request, usecase_id):
        usecase = get_object_or_404(Usecase.objects.for_user(request.user), pk=usecase_id)
        kind = (request.data.get("kind") or "").strip()

        if kind not in {choice for choice, _ in Job.KIND_CHOICES}:
            return Response(
                {"kind": [f"Unknown job kind {kind!r}."]}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            get_handler(kind)
        except LookupError as exc:
            return Response({"kind": [str(exc)]}, status=status.HTTP_501_NOT_IMPLEMENTED)

        job, created = enqueue(
            kind, user=request.user, usecase=usecase, payload=request.data.get("payload") or {}
        )
        return Response(
            JobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# RAG
# ---------------------------------------------------------------------------


class RagQueryView(APIView):
    """
    Ask a question of a scope's ingested documents.

    Synchronous: retrieval plus one completion, a few seconds. The old stack
    made this a RabbitMQ request/response with a 60s timeout because the RAG
    lived in another container; here it is a function call.
    """

    def post(self, request, usecase_id=None, instance_id=None):
        question = (request.data.get("query") or "").strip()
        if not question:
            return Response(
                {"query": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST
            )

        if instance_id is not None:
            instance = get_object_or_404(
                Instance.objects.for_user(request.user), pk=instance_id
            )
            usecase = instance.usecase
        else:
            instance = None
            usecase = get_object_or_404(
                Usecase.objects.for_user(request.user), pk=usecase_id
            )

        result = rag_query.answer(usecase=usecase, instance=instance, query=question)
        return Response(result)


# ---------------------------------------------------------------------------
# report PDFs
#
# One renderer and one route for every Markdown report, replacing seven
# near-identical view methods in the old backend.
# ---------------------------------------------------------------------------


class InstanceReportPdfView(APIView):
    """Download one of an instance's reports as a PDF."""

    def get(self, request, instance_id, slug):
        entry = INSTANCE_REPORTS.get(slug)
        if entry is None:
            return Response(
                {"slug": [f"Unknown report {slug!r}. Available: {', '.join(sorted(INSTANCE_REPORTS))}"]},
                status=status.HTTP_404_NOT_FOUND,
            )
        field, title = entry
        instance = get_object_or_404(Instance.objects.for_user(request.user), pk=instance_id)

        markdown = getattr(instance, field, "") or ""
        if not markdown.strip():
            return Response(
                {"detail": f"No {title.lower()} has been generated for this instance yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        pdf = render_pdf(markdown, title, subtitle=f"{instance.usecase.name} , {instance.name}")
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{slug}-{instance.id}.pdf"'
        return response


class DriftReportPdfView(APIView):
    """Download a drift comparison report as a PDF."""

    def get(self, request, drift_id):
        field, title = DRIFT_REPORTS["drift"]
        record = get_object_or_404(
            InstanceDataDrift.objects.filter(comparison_instance__usecase__user=request.user),
            pk=drift_id,
        )
        markdown = getattr(record, field, "") or ""
        if not markdown.strip():
            return Response(
                {"detail": "No drift report has been generated for this comparison yet."},
                status=status.HTTP_404_NOT_FOUND,
            )

        pdf = render_pdf(
            markdown,
            title,
            subtitle=f"{record.initial_instance.name} vs {record.comparison_instance.name}",
        )
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="drift-{record.id}.pdf"'
        return response


class InstanceDriftListView(generics.ListAPIView):
    """Drift comparisons where this instance is the later side."""

    serializer_class = DriftRecordSerializer

    def get_queryset(self):
        instance = get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )
        return InstanceDataDrift.objects.filter(comparison_instance=instance).select_related(
            "initial_instance", "comparison_instance"
        )


class InstanceBiasExplanationView(APIView):
    """
    Explain one bias metric for one feature in plain language.

    GET ?metric=fairness_metrics&feature=gender

    The metric and feature are query parameters, not path segments, because a
    feature is a column name and can hold characters a path segment cannot,
    such as a slash.
    """

    def get(self, request, instance_id):
        metric = (request.query_params.get("metric") or "").strip()
        feature = request.query_params.get("feature")
        if metric not in BIAS_METRICS:
            return Response(
                {"metric": [f"Unknown metric {metric!r}. Available: {', '.join(BIAS_METRICS)}"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not feature:
            return Response(
                {"feature": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST
            )

        instance = get_object_or_404(Instance.objects.for_user(request.user), pk=instance_id)
        section = (instance.analysis_results or {}).get(metric) or {}
        results = section.get("results") or {}
        if feature not in results:
            return Response(
                {"detail": f"No {metric.replace('_', ' ')} result for '{feature}' on this instance."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "metric": metric,
                "feature": feature,
                "explanation": explain_bias_metric(
                    metric, feature, results[feature], section.get("params")
                ),
            }
        )


# ---------------------------------------------------------------------------
# deleting uploads
# ---------------------------------------------------------------------------


class UsecaseFileDetailView(generics.RetrieveDestroyAPIView):
    """Remove a use case document, then re-index what remains."""

    serializer_class = UsecaseDataFileSerializer

    def get_queryset(self):
        usecase = get_object_or_404(
            Usecase.objects.for_user(self.request.user), pk=self.kwargs["usecase_id"]
        )
        return usecase.data_files.all()

    def perform_destroy(self, instance):
        usecase = instance.usecase
        instance.delete()
        # The chunks still describe the deleted document, so re-ingest. With no
        # documents left there is nothing to index , clear the chunks instead.
        if usecase.data_files.exists():
            enqueue("rag_ingest", user=self.request.user, usecase=usecase)
        else:
            DocumentChunk.objects.filter(usecase=usecase, instance=None).delete()


class InstanceFileDetailView(generics.RetrieveDestroyAPIView):
    """Remove an instance document, then re-index what remains."""

    serializer_class = InstanceDataFileSerializer

    def get_queryset(self):
        instance = get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )
        return instance.data_files.all()

    def perform_destroy(self, data_file):
        instance = data_file.instance
        data_file.delete()
        if instance.data_files.exists():
            enqueue("rag_ingest", user=self.request.user, instance=instance)
        else:
            DocumentChunk.objects.filter(instance=instance).delete()


class InstanceDatasetDetailView(generics.RetrieveDestroyAPIView):
    """Remove a dataset. Analyses already run against it keep their results."""

    serializer_class = InstanceDatasetFileSerializer

    def get_queryset(self):
        instance = get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )
        return instance.dataset_files.all()


class JobDetailView(generics.RetrieveAPIView):
    """Poll target. Scoped to the caller's own jobs."""

    serializer_class = JobSerializer

    def get_queryset(self):
        return Job.objects.for_user(self.request.user)


# ---------------------------------------------------------------------------
# downloads
#
# MEDIA_ROOT is never exposed as a static route. In the old stack
# /media/usecases/<uuid>/... was a public URL that the analysis services relied
# on; now they read from disk in-process and the only way out is through here.
# ---------------------------------------------------------------------------


class BaseDownloadView(APIView):
    """Serve one file, but only to someone who owns the object it hangs off."""

    model = None
    parent_lookup = None  # kwarg name -> filter path on the file model

    def get_object(self):
        raise NotImplementedError

    def get(self, request, **kwargs):
        data_file = self.get_object()
        if not data_file.file:
            raise Http404("File is missing.")
        try:
            handle = data_file.file.open("rb")
        except FileNotFoundError:
            raise Http404("File is missing from storage.")

        filename = data_file.file.name.rsplit("/", 1)[-1]
        response = FileResponse(handle, content_type=data_file.mime_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response


class UsecaseFileDownloadView(BaseDownloadView):
    def get_object(self):
        usecase = get_object_or_404(
            Usecase.objects.for_user(self.request.user), pk=self.kwargs["usecase_id"]
        )
        return get_object_or_404(UsecaseDataFile, pk=self.kwargs["pk"], usecase=usecase)


class InstanceFileDownloadView(BaseDownloadView):
    def get_object(self):
        instance = get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )
        return get_object_or_404(InstanceDataFile, pk=self.kwargs["pk"], instance=instance)


class InstanceDatasetDownloadView(BaseDownloadView):
    def get_object(self):
        instance = get_object_or_404(
            Instance.objects.for_user(self.request.user), pk=self.kwargs["instance_id"]
        )
        return get_object_or_404(
            InstanceDatasetFile, pk=self.kwargs["pk"], instance=instance
        )
