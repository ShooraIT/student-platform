from django.contrib import admin

from core.admin_mixins import AuditedAdmin

from . import services
from .models import Achievement, UserAchievement


@admin.register(Achievement)
class AchievementAdmin(AuditedAdmin):
    list_display = ["icon", "title", "kind", "count", "reward", "holders_count", "is_active", "order"]
    list_editable = ["is_active", "order"]
    autocomplete_fields = ["event"]

    @admin.display(description="Получили")
    def holders_count(self, obj):
        return obj.holders.count()


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ["user", "achievement", "created_at", "granted_by"]
    list_filter = ["achievement"]
    search_fields = ["user__last_name"]
    autocomplete_fields = ["user"]
    fields = ["user", "achievement"]

    def save_model(self, request, obj, form, change):
        if not change:
            services.grant(obj.user, obj.achievement, by=request.user)  # уведомление и награда
