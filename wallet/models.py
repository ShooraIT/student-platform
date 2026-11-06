from django.conf import settings
from django.db import models


class Transaction(models.Model):
    """Неизменяемая запись журнала степов. Баланс пользователя = сумма его операций."""

    class Kind(models.TextChoices):
        EVENT = "event_attendance", "Посещение мероприятия"
        TASK = "task_reward", "Выполнение задания"
        SURVEY = "survey_reward", "Прохождение опроса"
        VOTE = "vote_reward", "Участие в голосовании"
        ACHIEVEMENT = "achievement_reward", "Достижение"
        MANUAL = "manual_credit", "Ручное начисление"
        REVERSAL = "reversal", "Сторно"
        PURCHASE = "purchase", "Покупка"
        REFUND = "purchase_refund", "Возврат за покупку"

    EARNING_KINDS = [Kind.EVENT, Kind.TASK, Kind.SURVEY, Kind.VOTE, Kind.ACHIEVEMENT, Kind.MANUAL]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions", verbose_name="Студент"
    )
    amount = models.IntegerField("Сумма")
    kind = models.CharField("Тип", max_length=30, choices=Kind.choices)
    source_type = models.CharField("Источник", max_length=30, blank=True)
    source_id = models.PositiveBigIntegerField("ID источника", null=True, blank=True)
    reason = models.CharField("Описание", max_length=255)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Автор"
    )
    reverses = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by", verbose_name="Отменяет"
    )
    created_at = models.DateTimeField("Когда", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Операция со степами"
        verbose_name_plural = "Журнал степов"
        ordering = ["-created_at", "-id"]
        constraints = [
            # Идемпотентность автоматических начислений: одно начисление на источник
            models.UniqueConstraint(
                fields=["user", "kind", "source_type", "source_id"],
                condition=models.Q(source_id__isnull=False),
                name="uniq_reward_per_source",
            )
        ]

    def __str__(self):
        return f"{self.user} {self.amount:+d} — {self.reason}"
