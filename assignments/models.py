from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone

from core.models import Audience

ALLOWED_EXT = ["jpg", "jpeg", "png", "heic", "pdf", "docx", "pptx", "xlsx", "zip"]


def normalize(s):
    return " ".join(str(s).lower().replace("ё", "е").split())


class Task(Audience):
    class Kind(models.TextChoices):
        MANUAL = "manual", "Ручная проверка"
        AUTO = "auto", "Автопроверка (викторина)"
        QUEST = "quest", "Квест (вопросы по цепочке)"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"
        ARCHIVED = "archived", "Архив"

    title = models.CharField("Название", max_length=200)
    description = models.TextField("Описание")
    tracks = models.ManyToManyField(
        "career.Track", blank=True, related_name="career_tasks", verbose_name="Профессиональные направления"
    )
    cover = models.ImageField("Обложка", upload_to="tasks/", blank=True)
    kind = models.CharField("Тип", max_length=10, choices=Kind.choices, default=Kind.MANUAL)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.DRAFT)
    starts_at = models.DateTimeField("Доступно с", default=timezone.now)
    deadline = models.DateTimeField("Дедлайн")
    reward = models.PositiveIntegerField("Награда (максимум), степов", default=10)
    reward_limit = models.PositiveIntegerField("Награду получат первые N", null=True, blank=True)
    # ручная проверка
    allow_text = models.BooleanField("Ответ: текст", default=True)
    allow_link = models.BooleanField("Ответ: ссылка", default=False)
    allow_files = models.BooleanField("Ответ: файлы/фото (до 5 по 10 МБ)", default=False)
    # автопроверка
    attempts = models.PositiveSmallIntegerField("Число попыток", default=3)
    pass_percent = models.PositiveSmallIntegerField("Проходной порог, %", default=80)
    proportional = models.BooleanField(
        "Начислять пропорционально правильным ответам", default=False, help_text="Иначе — вся награда при достижении порога"
    )
    show_answers = models.BooleanField("Показывать правильные ответы после завершения", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Задание"
        verbose_name_plural = "Задания"
        ordering = ["deadline"]

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        now = timezone.now()
        return self.status == self.Status.PUBLISHED and self.starts_at <= now <= self.deadline

    def rewards_left(self):
        if self.reward_limit is None:
            return None
        return max(self.reward_limit - self.submissions.filter(status=Submission.Status.APPROVED).count(), 0)


class TaskQuestion(models.Model):
    class Kind(models.TextChoices):
        TEXT = "text", "Текстовый ответ"
        SINGLE = "single", "Один вариант"
        MULTI = "multi", "Несколько вариантов"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="questions")
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    kind = models.CharField("Тип", max_length=10, choices=Kind.choices, default=Kind.TEXT)
    text = models.TextField("Вопрос")
    options = models.TextField("Варианты", blank=True, help_text="Каждый вариант с новой строки")
    correct = models.TextField(
        "Правильные ответы", help_text="Каждый с новой строки. Для текстового — все допустимые варианты написания"
    )

    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы (для викторины и квеста)"
        ordering = ["order", "id"]

    def __str__(self):
        return self.text[:60]

    def option_list(self):
        return [o.strip() for o in self.options.splitlines() if o.strip()]

    def correct_set(self):
        return {normalize(c) for c in self.correct.splitlines() if c.strip()}

    def is_correct(self, answer):
        """answer: строка (text/single) или список строк (multi)."""
        if self.kind == self.Kind.MULTI:
            return {normalize(a) for a in (answer or [])} == self.correct_set()
        return normalize(answer or "") in self.correct_set()


class Submission(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "В процессе"
        SUBMITTED = "submitted", "На проверке"
        REVISION = "revision", "На доработке"
        APPROVED = "approved", "Принято"
        REJECTED = "rejected", "Отклонено"
        FAILED = "failed", "Не пройдено"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="submissions", verbose_name="Задание")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions", verbose_name="Студент"
    )
    status = models.CharField("Статус", max_length=15, choices=Status.choices, default=Status.SUBMITTED)
    text = models.TextField("Ответ", blank=True)
    link = models.URLField("Ссылка", blank=True)
    comment = models.TextField("Комментарий проверяющего", blank=True)
    awarded = models.PositiveIntegerField("Начислено", default=0)
    attempts_used = models.PositiveSmallIntegerField("Попыток использовано", default=0)
    best_percent = models.PositiveSmallIntegerField("Лучший результат, %", default=0)
    quest_step = models.PositiveSmallIntegerField("Шаг квеста", default=0)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Проверил"
    )
    reviewed_at = models.DateTimeField("Проверено", null=True, blank=True)
    submitted_at = models.DateTimeField("Отправлено", default=timezone.now)

    class Meta:
        verbose_name = "Ответ на задание"
        verbose_name_plural = "Ответы на задания"
        unique_together = [("task", "user")]
        ordering = ["submitted_at"]

    def __str__(self):
        return f"{self.user} — {self.task}"


class SubmissionFile(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to="submissions/%Y/%m/", validators=[FileExtensionValidator(ALLOWED_EXT)])

    def __str__(self):
        return self.file.name.rsplit("/", 1)[-1]

    @property
    def is_image(self):
        return self.file.name.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png")
