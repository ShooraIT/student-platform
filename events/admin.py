from django.utils import timezone
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from core.admin_mixins import AnnounceOnPublishAdmin, FirstYearAudienceGroupsMixin
from notifications.services import notify_many

from .models import Category, Event, Registration


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "color"]


class RegistrationInline(admin.TabularInline):
    model = Registration
    extra = 0
    fields = ["user", "status", "method", "attended_at"]
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Event)
class EventAdmin(FirstYearAudienceGroupsMixin, AnnounceOnPublishAdmin):
    announce_url = "/events/{pk}/"

    def announce_text(self, obj):
        return f"Новое мероприятие: {obj.title}, {timezone.localtime(obj.start):%d.%m в %H:%M}" + (f" (+{obj.reward})" if obj.reward else "")

    list_display = ["title", "start", "category", "status", "reward", "registered", "links"]
    list_filter = ["status", "category", "start"]
    search_fields = ["title"]
    date_hierarchy = "start"
    filter_horizontal = ["groups", "tracks"]
    actions = ["copy_events"]
    inlines = [RegistrationInline]
    fieldsets = (
        (None, {"fields": ("title", "description", "cover", "category", "status")}),
        ("Когда и где", {"fields": ("start", "end", "location", "employer")}),
        ("Профессиональные направления", {"fields": ("tracks",)}),
        ("Аудитория", {"fields": ("for_all", "courses", "groups")}),
        ("Запись", {"fields": ("registration_required", "capacity", "registration_deadline")}),
        ("Награда и отметка посещения", {"fields": ("reward", "checkin_qr", "checkin_code", "code_word", "checkin_list", "checkin_after_minutes")}),
    )

    @admin.display(description="Записано")
    def registered(self, obj):
        return obj.registered_count()

    @admin.display(description="Чек-ин")
    def links(self, obj):
        return format_html(
            '<a href="{}" target="_blank">QR-экран</a> · <a href="{}">Список</a>',
            reverse("events:staff_checkin", args=[obj.pk]),
            reverse("events:staff_attendees", args=[obj.pk]),
        )

    def save_model(self, request, obj, form, change):
        notify_change = None
        if change:
            old = Event.objects.get(pk=obj.pk)
            if old.status == Event.Status.PUBLISHED and obj.status == Event.Status.CANCELLED:
                notify_change = f"Мероприятие «{obj.title}» отменено"
            elif old.status == Event.Status.PUBLISHED and (old.start != obj.start or old.location != obj.location):
                notify_change = f"Мероприятие «{obj.title}» изменено: проверьте время и место"
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if notify_change:
            users = [r.user for r in obj.registrations.filter(status__in=Registration.ACTIVE).select_related("user")]
            notify_many(users, notify_change, f"/events/{obj.pk}/", "event")

    @admin.action(description="Создать копии (черновики) на неделю позже")
    def copy_events(self, request, queryset):
        from datetime import timedelta

        for e in queryset:
            groups = list(e.groups.all())
            tracks = list(e.tracks.all())
            e.pk = None
            e.start += timedelta(days=7)
            e.end += timedelta(days=7)
            e.status = Event.Status.DRAFT
            e.registration_deadline = None
            e.save()
            e.groups.set(groups)
            e.tracks.set(tracks)
        self.message_user(request, f"Создано копий: {queryset.count()}")
