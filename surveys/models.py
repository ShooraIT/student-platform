from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Audience


class Survey(Audience):
    class Kind(models.TextChoices):
        SURVEY = "survey", "Опрос"
        VOTE = "vote", "Голосование"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"

    class Results(models.TextChoices):
        AFTER_VOTE = "after_vote", "Сразу после голосования"
        AFTER_CLOSE = "after_close", "Только после закрытия"

    kind = models.CharField("Тип", max_length=10, choices=Kind.choices, default=Kind.SURVEY)
    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.DRAFT)
    opens_at = models.DateTimeField("Открывается", default=timezone.now)
    closes_at = models.DateTimeField("Закрывается")
    reward = models.PositiveIntegerField("Награда, степов", default=0)
    # голосование
    max_choices = models.PositiveSmallIntegerField("Голосов у участника", default=1)
    secret = models.BooleanField(
        "Тайное голосование", default=False, help_text="Хранится только факт участия, связи «студент — вариант» нет"
    )
    results_visibility = models.CharField(
        "Когда видны итоги", max_length=15, choices=Results.choices, default=Results.AFTER_CLOSE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Опрос / голосование"
        verbose_name_plural = "Опросы и голосования"
        ordering = ["-opens_at"]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        now = timezone.now()
        return self.status == self.Status.PUBLISHED and self.opens_at <= now <= self.closes_at

    @property
    def is_closed(self):
        return timezone.now() > self.closes_at

    def results_visible_to(self, user, voted):
        if user.is_staff_role:
            return True
        if self.kind != self.Kind.VOTE:
            return False
        return self.is_closed or (voted and self.results_visibility == self.Results.AFTER_VOTE)


class Question(models.Model):
    class Kind(models.TextChoices):
        SINGLE = "single", "Один вариант"
        MULTI = "multi", "Несколько вариантов"
        SELECT = "select", "Выпадающий список"
        SCALE5 = "scale5", "Шкала 1–5"
        SCALE10 = "scale10", "Шкала 1–10"
        SHORT = "short", "Короткий текст"
        LONG = "long", "Длинный текст"

    CHOICE_KINDS = [Kind.SINGLE, Kind.MULTI, Kind.SELECT]
    SCALE_KINDS = [Kind.SCALE5, Kind.SCALE10]

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    kind = models.CharField("Тип", max_length=10, choices=Kind.choices, default=Kind.SINGLE)
    text = models.CharField("Вопрос", max_length=500)
    options = models.TextField("Варианты", blank=True, help_text="Для вопросов с выбором — каждый с новой строки")
    required = models.BooleanField("Обязательный", default=True)

    class Meta:
        verbose_name = "Вопрос опроса"
        verbose_name_plural = "Вопросы опроса"
        ordering = ["order", "id"]

    def __str__(self):
        return self.text

    def option_list(self):
        return [o.strip() for o in self.options.splitlines() if o.strip()]

    def scale_range(self):
        return range(1, 11 if self.kind == self.Kind.SCALE10 else 6)


class VoteOption(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="vote_options")
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    title = models.CharField("Вариант / кандидат", max_length=200)
    description = models.TextField("Описание", blank=True)
    photo = models.ImageField("Фото", upload_to="votes/", blank=True)

    class Meta:
        verbose_name = "Вариант голосования"
        verbose_name_plural = "Варианты голосования"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Completion(models.Model):
    """Факт прохождения: один раз на студента."""

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="completions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="survey_completions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("survey", "user")]


class Answer(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="answers")
    completion = models.ForeignKey(Completion, null=True, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, null=True, on_delete=models.CASCADE, related_name="answers")
    vote_option = models.ForeignKey(VoteOption, null=True, on_delete=models.CASCADE, related_name="votes")
    value = models.TextField(blank=True)
