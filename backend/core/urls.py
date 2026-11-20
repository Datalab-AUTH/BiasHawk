from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    # infrastructure
    path("health", views.HealthView.as_view(), name="health"),
    path("csrf", views.CsrfView.as_view(), name="csrf"),
    path("me", views.MeView.as_view(), name="me"),
    # use cases
    path("usecases", views.UsecaseListView.as_view(), name="usecase-list"),
    path("usecases/<uuid:pk>", views.UsecaseDetailView.as_view(), name="usecase-detail"),
    path(
        "usecases/<uuid:usecase_id>/files",
        views.UsecaseFileListView.as_view(),
        name="usecase-file-list",
    ),
    path(
        "usecases/<uuid:usecase_id>/files/<uuid:pk>",
        views.UsecaseFileDetailView.as_view(),
        name="usecase-file-detail",
    ),
    path(
        "usecases/<uuid:usecase_id>/files/<uuid:pk>/download",
        views.UsecaseFileDownloadView.as_view(),
        name="usecase-file-download",
    ),
    # instances
    path("instances", views.InstanceListView.as_view(), name="instance-list"),
    path("instances/<uuid:pk>", views.InstanceDetailView.as_view(), name="instance-detail"),
    path(
        "instances/<uuid:instance_id>/files",
        views.InstanceFileListView.as_view(),
        name="instance-file-list",
    ),
    path(
        "instances/<uuid:instance_id>/files/<uuid:pk>",
        views.InstanceFileDetailView.as_view(),
        name="instance-file-detail",
    ),
    path(
        "instances/<uuid:instance_id>/files/<uuid:pk>/download",
        views.InstanceFileDownloadView.as_view(),
        name="instance-file-download",
    ),
    path(
        "instances/<uuid:instance_id>/datasets",
        views.InstanceDatasetListView.as_view(),
        name="instance-dataset-list",
    ),
    path(
        "instances/<uuid:instance_id>/datasets/<uuid:pk>",
        views.InstanceDatasetDetailView.as_view(),
        name="instance-dataset-detail",
    ),
    path(
        "instances/<uuid:instance_id>/datasets/<uuid:pk>/download",
        views.InstanceDatasetDownloadView.as_view(),
        name="instance-dataset-download",
    ),
    path(
        "usecases/<uuid:usecase_id>/jobs",
        views.UsecaseJobListView.as_view(),
        name="usecase-job-list",
    ),
    path(
        "usecases/<uuid:usecase_id>/rag/query",
        views.RagQueryView.as_view(),
        name="usecase-rag-query",
    ),
    path(
        "instances/<uuid:instance_id>/rag/query",
        views.RagQueryView.as_view(),
        name="instance-rag-query",
    ),
    path(
        "instances/<uuid:instance_id>/drift",
        views.InstanceDriftListView.as_view(),
        name="instance-drift-list",
    ),
    path(
        "instances/<uuid:instance_id>/bias-explanation",
        views.InstanceBiasExplanationView.as_view(),
        name="instance-bias-explanation",
    ),
    # jobs
    path(
        "instances/<uuid:instance_id>/jobs",
        views.InstanceJobListView.as_view(),
        name="instance-job-list",
    ),
    path("jobs/<uuid:pk>", views.JobDetailView.as_view(), name="job-detail"),
    # report PDFs
    path(
        "instances/<uuid:instance_id>/reports/<slug:slug>/pdf",
        views.InstanceReportPdfView.as_view(),
        name="instance-report-pdf",
    ),
    path("drift/<uuid:drift_id>/pdf", views.DriftReportPdfView.as_view(), name="drift-report-pdf"),
]
