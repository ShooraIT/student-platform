from django.conf import settings
from django.db import models


class Achievement(models.Model):
    class Kind(models.TextChoices):
        EVENTS = "events", "Посещено N мероприятий (можно ограничить категорией)"
        EMPLOYERS = "employers", "Побывал у N разных работодателей"
        TASKS = "tasks", "Принято N проектов (заданий)"
        MENTOR = "mentor", "N встреч с наставником"
        DIAGNOSTIC = "diagnostic", "Пройдена профдиагностика"
        MAIN_TRACK = "main_track", "Выбран основной трек"
        EVENT = "event", "Участие в конкретном мероприятии"
        MANUAL = "manual", "Только ручная выдача"

    title = models.CharField("Название", max_length=100)
    description = models.CharField("Описание", max_length=255)
    icon = models.CharField("Иконка", max_length=8, default="★")
    kind = models.CharField("Условие", max_length=20, choices=Kind.choices)
    count = models.PositiveIntegerField("N", default=1)
    category = models.ForeignKey("events.Category", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Только категория мероприятий")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, verbose_name="Мероприятие")
    reward = models.PositiveIntegerField("Награда, степов", default=0)
    is_active = models.BooleanField("Активно", default=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Значок"
        verbose_name_plural = "Карьерные значки"
        ordering = ["order", "id"]

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        if self.count < 1:
            raise ValidationError({"count": "Условие должно требовать хотя бы одну активность."})
        if self.kind == self.Kind.EVENT and not self.event_id:
            raise ValidationError({"event": "Для значка за конкретное мероприятие выберите мероприятие."})
        if self.category_id and self.kind != self.Kind.EVENTS:
            raise ValidationError({"category": "Категорию можно задать только для значка за посещение мероприятий."})

    def __str__(self):
        return f"{self.icon} {self.title}"


class UserAchievement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements", verbose_name="Студент")
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name="holders", verbose_name="Достижение")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Выдал вручную")
    created_at = models.DateTimeField("Получено", auto_now_add=True)

    class Meta:
        verbose_name = "Полученное достижение"
        verbose_name_plural = "Полученные достижения"
        unique_together = [("user", "achievement")]
        ordering = ["-created_at"]
