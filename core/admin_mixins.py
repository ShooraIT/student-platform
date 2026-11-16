from django.contrib import admin
from django.utils import timezone

from .models import AuditLog


class FirstYearAudienceGroupsMixin:
    """В формах активностей доступны только актуальные группы первого курса."""

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "groups":
            from accounts.models import StudyGroup

            kwargs["queryset"] = StudyGroup.objects.filter(is_active=True, course=1).order_by("name")
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class AuditedAdmin(admin.ModelAdmin):
    """Пишет создание, изменение и удаление объектов в журнал действий (п. 13.3 ТЗ)."""

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditLog.log(
            request.user,
            f"{'Изменение' if change else 'Создание'}: {obj._meta.verbose_name}",
            obj,
            fields=list(form.changed_data) if change else [],
        )

    def delete_model(self, request, obj):
        AuditLog.log(request.user, f"Удаление: {obj._meta.verbose_name}", obj)
        super().delete_model(request, obj)


class AnnounceOnPublishAdmin(AuditedAdmin):
    """При первой публикации объекта уведомляет студентов его аудитории («Новое для вас»)."""

    publish_status = "published"
    announce_url = ""  # например "/events/{pk}/"

    def announce_text(self, obj):
        return f"Новое: {obj}"

    def save_model(self, request, obj, form, change):
        was_published = change and type(obj).objects.filter(pk=obj.pk, status=self.publish_status).exists()
        super().save_model(request, obj, form, change)
        obj._announce = obj.status == self.publish_status and not was_published
        start = getattr(obj, "starts_at", None) or getattr(obj, "opens_at", None)
        if obj._announce and start and start > timezone.now():
            obj._announce = False  # ещё не видно студентам — не анонсируем, чтобы ссылка не вела в пустоту
            self.message_user(request, "Публикация откроется позже — уведомление студентам не отправлено. Сделайте объявление в момент открытия.")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)  # группы аудитории сохраняются здесь
        obj = form.instance
        if getattr(obj, "_announce", False):
            from notifications.services import notify_many

            n = notify_many(obj.audience_students(), self.announce_text(obj), self.announce_url.format(pk=obj.pk), "new_content")
            self.message_user(request, f"Студенты получили уведомление о публикации: {n}")
