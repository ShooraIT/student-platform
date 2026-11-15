import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Audience


class Category(models.Model):
    name = models.CharField("Название", max_length=60, unique=True)
    color = models.CharField("Цвет", max_length=7, default="#cb563d", help_text="Палитра 01:17: #f1a627 жёлтый, #cb563d терракота, #2e7d4f зелёный, #1d1f27 графит")

    class Meta:
        verbose_name = "Категория мероприятий"
        verbose_name_plural = "Категории мероприятий"
        ordering = ["name"]

    def __str__(self):
        return self.name


def gen_code():
    return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))


class Event(Audience):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"
        CANCELLED = "cancelled", "Отменено"

    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание")
    cover = models.ImageField("Обложка", upload_to="events/", blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="Категория")
    tracks = models.ManyToManyField(
        "career.Track", blank=True, related_name="career_events", verbose_name="Профессиональные направления"
    )
    start = models.DateTimeField("Начало")
    end = models.DateTimeField("Окончание")
    location = models.CharField("Место", max_length=200)
    employer = models.ForeignKey("career.Employer", null=True, blank=True, on_delete=models.SET_NULL, related_name="events", verbose_name="Работодатель", help_text="Экскурсия, профпроба или встреча с компанией")
    registration_required = models.BooleanField("Обязательна запись", default=False)
    capacity = models.PositiveIntegerField("Лимит мест", null=True, blank=True)
    registration_deadline = models.DateTimeField("Запись до", null=True, blank=True, help_text="По умолчанию — до начала")
    reward = models.PositiveIntegerField("Награда, степов", default=0)
    checkin_qr = models.BooleanField("Отметка по QR-коду", default=True)
    checkin_code = models.BooleanField("Отметка по кодовому слову", default=False)
    checkin_list = models.BooleanField("Отметка по списку", default=True)
    code_word = models.CharField("Кодовое слово", max_length=20, default=gen_code)
    checkin_after_minutes = models.PositiveIntegerField("Чек-ин открыт после окончания, мин", default=30)
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Мероприятие"
        verbose_name_plural = "Мероприятия"
        ordering = ["start"]

    def __str__(self):
        return f"{self.title} ({self.start:%d.%m.%Y})"

    @property
    def checkin_open(self):
        now = timezone.now()
        return (
            self.status == self.Status.PUBLISHED
            and self.start - timedelta(minutes=15) <= now <= self.end + timedelta(minutes=self.checkin_after_minutes)
        )

    @property
    def is_past(self):
        return timezone.now() > self.end

    @property
    def registration_open(self):
        deadline = self.registration_deadline or self.start
        return self.status == self.Status.PUBLISHED and timezone.now() < deadline

    def registered_count(self):
        return self.registrations.filter(status__in=Registration.ACTIVE).count()

    def seats_left(self):
        if self.capacity is None:
            return None
        return max(self.capacity - self.registered_count(), 0)


class Registration(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Записан"
        WAITLIST = "waitlist", "Лист ожидания"
        CANCELLED = "cancelled", "Отменил запись"
        ATTENDED = "attended", "Посетил"

    class Method(models.TextChoices):
        QR = "qr", "QR-код"
        CODE = "code", "Кодовое слово"
        LIST = "list", "Отметка администратором"

    ACTIVE = [Status.REGISTERED, Status.ATTENDED]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations", verbose_name="Мероприятие")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registrations", verbose_name="Студент"
    )
    status = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.REGISTERED)
    method = models.CharField("Способ отметки", max_length=10, choices=Method.choices, blank=True)
    attended_at = models.DateTimeField("Время отметки", null=True, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField("Записался", auto_now_add=True)

    class Meta:
        verbose_name = "Запись на мероприятие"
        verbose_name_plural = "Записи на мероприятия"
        unique_together = [("event", "user")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} — {self.event}"


class CodeAttempt(models.Model):
    """Неудачные попытки ввода кодового слова — защита от подбора."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
