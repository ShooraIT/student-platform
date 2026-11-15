from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.admin_mixins import AnnounceOnPublishAdmin

from .models import Question, Survey, VoteOption


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    fields = [("order", "kind", "required"), "text", "options"]


class VoteOptionInline(admin.TabularInline):
    model = VoteOption
    extra = 0
    fields = ["order", "title", "description", "photo"]


@admin.register(Survey)
class SurveyAdmin(AnnounceOnPublishAdmin):
    announce_url = "/surveys/{pk}/"

    def announce_text(self, obj):
        return f"{obj.get_kind_display()}: {obj.title}" + (f" (+{obj.reward})" if obj.reward else "")

    list_display = ["title", "kind", "status", "opens_at", "closes_at", "reward", "answers", "results_link"]
    list_filter = ["kind", "status"]
    search_fields = ["title"]
    filter_horizontal = ["groups", "tracks"]
    inlines = [QuestionInline, VoteOptionInline]
    fieldsets = (
        (None, {"fields": ("kind", "title", "description", "status")}),
        ("Сроки и награда", {"fields": ("opens_at", "closes_at", "reward")}),
        ("Профессиональные направления", {"fields": ("tracks",)}),
        ("Аудитория", {"fields": ("for_all", "courses", "groups")}),
        ("Голосование", {"fields": ("max_choices", "secret", "results_visibility"),
                         "description": "Для опроса заполните «Вопросы», для голосования — «Варианты голосования»"}),
    )

    @admin.display(description="Ответов")
    def answers(self, obj):
        return obj.completions.count()

    @admin.display(description="")
    def results_link(self, obj):
        return format_html('<a href="{}">Результаты</a>', reverse("surveys:results", args=[obj.pk]))

    def get_readonly_fields(self, request, obj=None):
        # Режим тайности нельзя менять после первых голосов
        if obj and obj.completions.exists():
            return ["secret", "kind"]
        return []
