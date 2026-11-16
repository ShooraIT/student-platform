from django.contrib import admin
from django.utils import timezone

from core.admin_mixins import AuditedAdmin
from . import services as career_services

from .models import (
    DiagOption, DiagOptionWeight, DiagQuestion, DiagResult, DiagScale, DiagTest, Employer, ExternalAchievement, FundIssue, FundItem,
    MentorBooking, MentorSlot, Resume, RouteStage, StageCondition, Track, TrackEnrollment, TrackItem, Vacancy,
)


class TrackItemInline(admin.TabularInline):
    model = TrackItem
    extra = 1
    autocomplete_fields = ["event", "task"]


@admin.register(Track)
class TrackAdmin(AuditedAdmin):
    list_display = ["title", "tagline", "is_active", "order"]
    list_editable = ["order", "is_active"]
    prepopulated_fields = {"slug": ["title"]}
    search_fields = ["title"]
    fieldsets = (
        (None, {"fields": ("title", "slug", "tagline", "description", "position_title", "is_active", "order", "color", "cover")}),
        ("Профиль должности", {"fields": ("duties", "knowledge", "skills", "specialties")}),
    )
    inlines = [TrackItemInline]


@admin.register(Vacancy)
class VacancyAdmin(AuditedAdmin):
    list_display = ["title", "employer", "track", "location", "closes_at", "is_active"]
    list_filter = ["track", "employer", "is_active"]
    search_fields = ["title", "employer__name", "description"]


@admin.register(TrackEnrollment)
class TrackEnrollmentAdmin(admin.ModelAdmin):
    list_display = ["user", "track", "is_main", "created_at"]
    list_filter = ["track", "is_main"]
    search_fields = ["user__last_name", "user__first_name"]


@admin.register(Employer)
class EmployerAdmin(AuditedAdmin):
    list_display = ["name", "industry", "is_active"]
    list_filter = ["tracks", "is_active"]
    search_fields = ["name"]
    filter_horizontal = ["tracks"]


class ScaleInline(admin.TabularInline):
    model = DiagScale
    extra = 1
    filter_horizontal = ["tracks"]


class QuestionInline(admin.TabularInline):
    model = DiagQuestion
    extra = 1
    show_change_link = True


@admin.register(DiagTest)
class DiagTestAdmin(AuditedAdmin):
    list_display = ["title", "is_active"]
    inlines = [ScaleInline, QuestionInline]


class OptionInline(admin.TabularInline):
    model = DiagOption
    extra = 2
    show_change_link = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # шкалы только этого теста
        if db_field.name == "scale" and request.resolver_match.kwargs.get("object_id"):
            q = DiagQuestion.objects.filter(pk=request.resolver_match.kwargs["object_id"]).first()
            if q:
                kwargs["queryset"] = DiagScale.objects.filter(test=q.test)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OptionWeightInline(admin.TabularInline):
    model = DiagOptionWeight
    extra = 1


@admin.register(DiagOption)
class DiagOptionAdmin(admin.ModelAdmin):
    list_display = ["text", "question"]
    search_fields = ["text"]
    inlines = [OptionWeightInline]


@admin.register(DiagQuestion)
class DiagQuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "test", "order"]
    list_filter = ["test"]
    inlines = [OptionInline]


@admin.register(DiagResult)
class DiagResultAdmin(admin.ModelAdmin):
    list_display = ["user", "test", "created_at"]
    list_filter = ["test"]
    readonly_fields = ["user", "test", "scores", "recommended", "created_at"]


class ConditionInline(admin.TabularInline):
    model = StageCondition
    extra = 1


@admin.register(RouteStage)
class RouteStageAdmin(AuditedAdmin):
    list_display = ["order", "title", "deadline"]
    list_display_links = ["title"]
    inlines = [ConditionInline]


class BookingInline(admin.TabularInline):
    model = MentorBooking
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(MentorSlot)
class MentorSlotAdmin(admin.ModelAdmin):
    list_display = ["topic", "mentor", "track", "start", "capacity", "held", "is_cancelled"]
    list_filter = ["track", "held", "is_cancelled"]
    autocomplete_fields = ["mentor"]
    inlines = [BookingInline]


@admin.register(ExternalAchievement)
class ExternalAchievementAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "user__last_name"]


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ["user", "headline", "public", "updated_at"]
    readonly_fields = ["token"]


@admin.register(FundItem)
class FundItemAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "stock", "issued", "on_hands_now", "asset_path"]
    list_filter = ["kind"]

    @admin.display(description="Выдано всего")
    def issued(self, obj):
        return obj.issues.count()

    @admin.display(description="Сейчас на руках")
    def on_hands_now(self, obj):
        return obj.on_hands() if obj.kind == FundItem.Kind.LOAN else "—"


@admin.register(FundIssue)
class FundIssueAdmin(admin.ModelAdmin):
    list_display = ["item", "user", "size", "issued_at", "returned_at"]
    list_filter = ["item", "returned_at"]
    autocomplete_fields = ["user"]
    search_fields = ["user__last_name", "user__first_name"]
    actions = ["mark_returned"]

    def save_model(self, request, obj, form, change):
        if not change:
            created = career_services.issue_fund(obj.item, obj.user, request.user, size=obj.size, note=obj.note)
            obj.pk = created.pk
            obj.issued_at = created.issued_at
            return
        previous = FundIssue.objects.get(pk=obj.pk)
        if obj.returned_at and not previous.returned_at:
            career_services.return_fund(previous, note=obj.note)
            return
        super().save_model(request, obj, form, change)

    @admin.action(description="Отметить возврат")
    def mark_returned(self, request, qs):
        n = 0
        for issue in qs.filter(returned_at__isnull=True).select_related("item"):
            try:
                career_services.return_fund(issue)
                n += 1
            except career_services.CareerError as exc:
                self.message_user(request, f"{issue}: {exc}", level="WARNING")
        self.message_user(request, f"Возвращено: {n}")
