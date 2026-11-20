from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from core.models import (
    ErrorLog,
    Instance,
    InstanceDataDrift,
    InstanceDataFile,
    InstanceDatasetFile,
    Usecase,
    UsecaseDataFile,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "name", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "name"]
    readonly_fields = ["id", "date_joined", "last_login"]

    fieldsets = [
        (None, {"fields": ["id", "email", "password"]}),
        (_("Personal info"), {"fields": ["name"]}),
        (
            _("Permissions"),
            {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]},
        ),
        (_("Important dates"), {"fields": ["last_login", "date_joined"]}),
    ]

    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": ["email", "name", "password1", "password2"],
            },
        ),
    ]


class UsecaseDataFileInline(admin.TabularInline):
    model = UsecaseDataFile
    extra = 0
    fields = ["file", "mime_type", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Usecase)
class UsecaseAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "description", "user__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [UsecaseDataFileInline]
    list_select_related = ["user"]


class InstanceDataFileInline(admin.TabularInline):
    model = InstanceDataFile
    extra = 0
    fields = ["file", "mime_type", "created_at"]
    readonly_fields = ["created_at"]


class InstanceDatasetFileInline(admin.TabularInline):
    model = InstanceDatasetFile
    extra = 0
    fields = ["file", "kind", "mime_type", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = ["name", "usecase", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "description", "usecase__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [InstanceDataFileInline, InstanceDatasetFileInline]
    list_select_related = ["usecase"]


@admin.register(InstanceDataDrift)
class InstanceDataDriftAdmin(admin.ModelAdmin):
    list_display = [
        "initial_instance",
        "comparison_instance",
        "drift_detected",
        "bias_drift_detected",
        "created_at",
    ]
    list_filter = ["drift_detected", "bias_drift_detected"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ["origin", "created_at"]
    list_filter = ["origin", "created_at"]
    search_fields = ["origin", "message"]
    readonly_fields = ["id", "origin", "message", "created_at"]

    def has_add_permission(self, request):
        return False
