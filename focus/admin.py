from django.contrib import admin
from .models import FocusSession


@admin.register(FocusSession)
class FocusSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "title",
        "status",
        "speed_rate",
        "accumulated_virtual_seconds",
        "total_planned_virtual_seconds",
        "created_at",
    ]
    list_filter = ["status", "speed_rate", "created_at"]
    search_fields = ["title", "user__username"]
    raw_id_fields = ["user"]
