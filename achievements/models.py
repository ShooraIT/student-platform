from django.conf import settings
from django.db import models


class Achievement(models.Model):
    class Kind(models.TextChoices):
        EVENTS = "events", "Посещено N мероприятий"
        TASKS = "tasks", "Выполнено N заданий"
        SURVEYS = "surveys", "Пройдено N опросов / голосований"
        EARNED = "earned", "Заработано N степов за всё время"
        FIRST_PURCHASE = "first_purchase", "Первая покупка"
        EVENT = "event", "Участие в конкретном мероприятии"
        MANUAL = "manual", "Только ручная выдача"

    title = models.CharField("Название", max_length=100)
    description = models.CharField("Описание", max_length=255)
    icon = models.CharField("Иконка (эмодзи)", max_length=8, default="🏅")
    kind = models.CharField("Условие", max_length=20, choices=Kind.choices)
    count = models.PositiveIntegerField("N", default=1)
    category = models.ForeignKey("events.Category", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Только категория мероприятий")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, verbose_name="Мероприятие")
    reward = models.PositiveIntegerField("Награда, степов", default=0)
    is_active = models.BooleanField("Активно", default=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Достижение"
        verbose_name_plural = "Достижения"
        ordering = ["order", "id"]

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
