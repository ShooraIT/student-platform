from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.admin_mixins import AnnounceOnPublishAdmin

from .models import Submission, Task, TaskQuestion


class QuestionInline(admin.StackedInline):
    model = TaskQuestion
    extra = 0
    fields = [("order", "kind"), "text", "options", "correct"]


@admin.register(Task)
class TaskAdmin(AnnounceOnPublishAdmin):
    announce_url = "/tasks/{pk}/"

    def announce_text(self, obj):
        return f"Новое задание: {obj.title}" + (f" (+{obj.reward})" if obj.reward else "")

    list_display = ["title", "kind", "status", "deadline", "reward", "submitted", "review_link"]
    list_filter = ["kind", "status"]
    search_fields = ["title"]
    filter_horizontal = ["groups", "tracks"]
    inlines = [QuestionInline]
    fieldsets = (
        (None, {"fields": ("title", "description", "cover", "kind", "status")}),
        ("Сроки и награда", {"fields": ("starts_at", "deadline", "reward", "reward_limit")}),
        ("Профессиональные направления", {"fields": ("tracks",)}),
        ("Аудитория", {"fields": ("for_all", "courses", "groups")}),
        ("Ручная проверка: формат ответа", {"fields": ("allow_text", "allow_link", "allow_files")}),
        ("Викторина / квест", {"fields": ("attempts", "pass_percent", "proportional", "show_answers")}),
    )

    @admin.display(description="Ответов")
    def submitted(self, obj):
        return obj.submissions.count()

    @admin.display(description="")
    def review_link(self, obj):
        if obj.kind != Task.Kind.MANUAL:
            return ""
        return format_html('<a href="{}?task={}">Проверить</a>', reverse("assignments:review"), obj.pk)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["task", "user", "status", "awarded", "submitted_at", "reviewed_by"]
    list_filter = ["status", "task"]
    search_fields = ["user__last_name", "task__title"]
    readonly_fields = [f.name for f in Submission._meta.fields]

    def has_add_permission(self, request):
        return False
