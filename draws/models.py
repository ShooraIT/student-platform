from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Audience


class Draw(Audience):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Приём заявок"
        DONE = "done", "Проведён"

    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    photo = models.ImageField("Фото", upload_to="draws/", blank=True)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.DRAFT)
    entries_open = models.DateTimeField("Приём заявок с", default=timezone.now)
    entries_close = models.DateTimeField("Приём заявок до")
    draw_at = models.DateTimeField("Время розыгрыша", help_text="Не раньше окончания приёма заявок")
    # результаты (для проверяемости)
    seed = models.CharField("Зерно (seed)", max_length=64, blank=True, editable=False)
    participants_hash = models.CharField("Хэш списка участников", max_length=64, blank=True, editable=False)
    participants_count = models.PositiveIntegerField("Участников", default=0, editable=False)
    drawn_at = models.DateTimeField("Проведён", null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Розыгрыш"
        verbose_name_plural = "Розыгрыши"
        ordering = ["-draw_at"]

    def __str__(self):
        return self.title

    @property
    def accepting(self):
        now = timezone.now()
        return self.status == self.Status.PUBLISHED and self.entries_open <= now <= self.entries_close


class DrawCondition(models.Model):
    class Kind(models.TextChoices):
        EVENTS_COUNT = "events_count", "Посетил не менее N мероприятий за период"
        EVENT = "event", "Посетил конкретное мероприятие"
        TASK = "task", "Выполнил конкретное задание"
        SURVEY = "survey", "Прошёл конкретный опрос / голосование"

    draw = models.ForeignKey(Draw, on_delete=models.CASCADE, related_name="conditions")
    kind = models.CharField("Условие", max_length=20, choices=Kind.choices)
    count = models.PositiveIntegerField("N", null=True, blank=True)
    period_start = models.DateField("Период с", null=True, blank=True)
    period_end = models.DateField("Период по", null=True, blank=True)
    category = models.ForeignKey("events.Category", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Только категория")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, verbose_name="Мероприятие")
    task = models.ForeignKey("assignments.Task", null=True, blank=True, on_delete=models.CASCADE, verbose_name="Задание")
    survey = models.ForeignKey("surveys.Survey", null=True, blank=True, on_delete=models.CASCADE, verbose_name="Опрос")

    class Meta:
        verbose_name = "Условие участия"
        verbose_name_plural = "Условия участия (должны выполняться все)"

    def __str__(self):
        if self.kind == self.Kind.EVENTS_COUNT:
            p = f" с {self.period_start:%d.%m} по {self.period_end:%d.%m}" if self.period_start and self.period_end else ""
            c = f" («{self.category}»)" if self.category_id else ""
            return f"Посетить {self.count or 0} мероприятий{c}{p}"
        if self.kind == self.Kind.EVENT:
            return f"Посетить «{self.event.title if self.event else '?'}»"
        if self.kind == self.Kind.TASK:
            return f"Выполнить задание «{self.task.title if self.task else '?'}»"
        return f"Пройти «{self.survey.title if self.survey else '?'}»"


class DrawPrize(models.Model):
    draw = models.ForeignKey(Draw, on_delete=models.CASCADE, related_name="prizes")
    title = models.CharField("Приз", max_length=200)
    quantity = models.PositiveIntegerField("Количество", default=1)

    class Meta:
        verbose_name = "Приз"
        verbose_name_plural = "Призы"

    def __str__(self):
        return self.title


class DrawEntry(models.Model):
    draw = models.ForeignKey(Draw, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="draw_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("draw", "user")]


class DrawWinner(models.Model):
    draw = models.ForeignKey(Draw, on_delete=models.CASCADE, related_name="winners")
    prize = models.ForeignKey(DrawPrize, on_delete=models.CASCADE, related_name="winners")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="draw_wins")
    order = models.OneToOneField("shop.Order", null=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = [("draw", "user")]
