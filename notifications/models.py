from django.conf import settings
from django.db import models

# Категории уведомлений и пуш по умолчанию (п. 11.2 ТЗ)
CATEGORIES = {
    "new_content": ("Новые мероприятия, задания, опросы для меня", False),
    "reminder": ("Напоминания о мероприятиях, на которые я записан", True),
    "event": ("Отмена или перенос мероприятия, освободилось место", True),
    "credit": ("Начисление степов", False),
    "task": ("Проверка моих заданий", True),
    "order": ("Заказ готов к выдаче или отменён", True),
    "draw": ("Выигрыш в розыгрыше", True),
    "achievement": ("Новое достижение", False),
    "announcement": ("Объявления администрации", True),
    "stock": ("Заканчивается товар (для администраторов)", True),
}


class Notification(models.Model):
    class Push(models.TextChoices):
        NONE = "none", "Не нужен"
        PENDING = "pending", "В очереди"
        SENT = "sent", "Отправлен"
        FAILED = "failed", "Ошибка"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications", verbose_name="Получатель"
    )
    kind = models.CharField("Тип", max_length=30, default="info")
    text = models.CharField("Текст", max_length=500)
    url = models.CharField("Ссылка", max_length=255, blank=True)
    is_read = models.BooleanField("Прочитано", default=False)
    push = models.CharField("Пуш", max_length=10, choices=Push.choices, default=Push.NONE, db_index=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]

    def __str__(self):
        return self.text


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField("Endpoint", max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField("Устройство", max_length=300, blank=True)
    created_at = models.DateTimeField("Подключено", auto_now_add=True)

    class Meta:
        verbose_name = "Подписка на пуш"
        verbose_name_plural = "Подписки на пуш"

    def __str__(self):
        return f"{self.user} — {self.user_agent[:40]}"

    def as_info(self):
        return {"endpoint": self.endpoint, "keys": {"p256dh": self.p256dh, "auth": self.auth}}


class PushPrefs(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_prefs")
    prefs = models.JSONField(default=dict)

    def enabled(self, kind):
        default = CATEGORIES.get(kind, ("", True))[1]
        return self.prefs.get(kind, default)

    @classmethod
    def for_user(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj


class Broadcast(models.Model):
    """Объявление администрации выбранной аудитории (п. 11.3 ТЗ)."""

    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, verbose_name="Автор")
    text = models.CharField("Текст", max_length=300)
    url = models.CharField("Ссылка", max_length=255, blank=True)
    audience = models.CharField("Аудитория", max_length=200)
    recipients = models.PositiveIntegerField("Получателей", default=0)
    created_at = models.DateTimeField("Отправлено", auto_now_add=True)

    class Meta:
        verbose_name = "Объявление"
        verbose_name_plural = "Объявления"
        ordering = ["-created_at"]
