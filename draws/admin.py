from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html

from core.admin_mixins import AnnounceOnPublishAdmin

from .models import Draw, DrawCondition, DrawPrize


class ConditionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        K = DrawCondition.Kind
        need = {K.EVENTS_COUNT: "count", K.EVENT: "event", K.TASK: "task", K.SURVEY: "survey"}
        for f in self.forms:
            d = getattr(f, "cleaned_data", None)
            if not d or d.get("DELETE"):
                continue
            field = need.get(d.get("kind"))
            if field and not d.get(field):
                raise ValidationError(f"Условие «{K(d['kind']).label}»: заполните поле «{DrawCondition._meta.get_field(field).verbose_name}»")


class ConditionInline(admin.StackedInline):
    model = DrawCondition
    formset = ConditionFormSet
    extra = 0
    autocomplete_fields = ["event", "task", "survey"]
    fields = ["kind", ("count", "period_start", "period_end", "category"), "event", "task", "survey"]


class PrizeInline(admin.TabularInline):
    model = DrawPrize
    extra = 1


@admin.register(Draw)
class DrawAdmin(AnnounceOnPublishAdmin):
    announce_url = "/draws/{pk}/"

    def announce_text(self, obj):
        return f"Новый розыгрыш: {obj.title}"

    list_display = ["title", "status", "entries_close", "draw_at", "entries", "manage"]
    list_filter = ["status"]
    filter_horizontal = ["groups"]
    inlines = [PrizeInline, ConditionInline]
    readonly_fields = ["seed", "participants_hash", "participants_count", "drawn_at"]
    fieldsets = (
        (None, {"fields": ("title", "description", "photo", "status")}),
        ("Сроки", {"fields": ("entries_open", "entries_close", "draw_at")}),
        ("Аудитория", {"fields": ("for_all", "courses", "groups")}),
        ("Результат", {"fields": readonly_fields}),
    )

    @admin.display(description="Участников")
    def entries(self, obj):
        return obj.entries.count()

    @admin.display(description="")
    def manage(self, obj):
        return format_html('<a href="{}">Участники и запуск</a>', reverse("draws:staff", args=[obj.pk]))

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj and obj.status == Draw.Status.DONE:
            ro += ["status", "entries_open", "entries_close", "draw_at"]
        return ro
