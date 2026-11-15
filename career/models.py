"""Карьерный проект 01:17: треки, работодатели, профдиагностика, маршрут первокурсника,
наставники-старшекурсники, портфолио и резюме, учёт велком-наборов и фонда одежды."""
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .storage import PrivatePortfolioStorage

U = settings.AUTH_USER_MODEL


# ---------- треки и работодатели ----------

class Track(models.Model):
    title = models.CharField("Название", max_length=80, unique=True)
    slug = models.SlugField("Код", max_length=40, unique=True)
    tagline = models.CharField("Фраза линейки", max_length=120, blank=True, help_text="Например, «Спокойно, я уже подключился.»")
    description = models.TextField("Описание", blank=True)
    cover = models.ImageField("Обложка", upload_to="tracks/", blank=True)
    color = models.CharField("Цвет", max_length=7, default="#cb563d")
    specialties = models.CharField("Специальности", max_length=200, blank=True, help_text="Коды через запятую, например 09.02.07")
    is_active = models.BooleanField("Активен", default=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Профессиональный трек"
        verbose_name_plural = "Профессиональные треки"
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class TrackItem(models.Model):
    """Активность трека. Засчитывается автоматически по данным платформы."""

    class Kind(models.TextChoices):
        EVENT = "event", "Мероприятие"
        TASK = "task", "Задание (проект)"
        MENTOR = "mentor", "Встреча с наставником трека"
        DIAGNOSTIC = "diagnostic", "Профдиагностика"

    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="items", verbose_name="Трек")
    title = models.CharField("Название", max_length=150)
    kind = models.CharField("Тип", max_length=12, choices=Kind.choices)
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, related_name="track_items", verbose_name="Мероприятие")
    task = models.ForeignKey("assignments.Task", null=True, blank=True, on_delete=models.CASCADE, related_name="track_items", verbose_name="Задание")
    required = models.BooleanField("Обязательная", default=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Активность трека"
        verbose_name_plural = "Активности трека"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class TrackEnrollment(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="track_enrollments", verbose_name="Студент")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="enrollments", verbose_name="Трек")
    is_main = models.BooleanField("Основной", default=False)
    created_at = models.DateTimeField("Начат", auto_now_add=True)

    class Meta:
        verbose_name = "Участие в треке"
        verbose_name_plural = "Участие в треках"
        unique_together = [("user", "track")]
        ordering = ["-is_main", "created_at"]


class Employer(models.Model):
    name = models.CharField("Компания", max_length=150, unique=True)
    industry = models.CharField("Отрасль", max_length=100, blank=True)
    description = models.TextField("О компании", blank=True)
    website = models.URLField("Сайт", blank=True)
    logo = models.ImageField("Логотип", upload_to="employers/", blank=True)
    tracks = models.ManyToManyField(Track, blank=True, related_name="employers", verbose_name="Треки")
    is_active = models.BooleanField("Показывать", default=True)

    class Meta:
        verbose_name = "Работодатель"
        verbose_name_plural = "Работодатели"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ---------- профдиагностика ----------

class DiagTest(models.Model):
    title = models.CharField("Название", max_length=150)
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Доступен", default=True)

    class Meta:
        verbose_name = "Профдиагностика"
        verbose_name_plural = "Профдиагностика"

    def __str__(self):
        return self.title


class DiagScale(models.Model):
    test = models.ForeignKey(DiagTest, on_delete=models.CASCADE, related_name="scales", verbose_name="Тест")
    name = models.CharField("Шкала", max_length=80, help_text="Например, «Техника и цифра»")
    description = models.CharField("Что значит высокий балл", max_length=255, blank=True)
    tracks = models.ManyToManyField(Track, blank=True, related_name="scales", verbose_name="Рекомендуемые треки")

    class Meta:
        verbose_name = "Шкала"
        verbose_name_plural = "Шкалы"

    def __str__(self):
        return self.name


class DiagQuestion(models.Model):
    test = models.ForeignKey(DiagTest, on_delete=models.CASCADE, related_name="questions", verbose_name="Тест")
    text = models.CharField("Вопрос", max_length=300)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Вопрос диагностики"
        verbose_name_plural = "Вопросы диагностики"
        ordering = ["order", "id"]

    def __str__(self):
        return self.text


class DiagOption(models.Model):
    question = models.ForeignKey(DiagQuestion, on_delete=models.CASCADE, related_name="options", verbose_name="Вопрос")
    text = models.CharField("Ответ", max_length=200)
    scale = models.ForeignKey(DiagScale, on_delete=models.CASCADE, verbose_name="Добавляет баллы шкале")
    points = models.PositiveSmallIntegerField("Баллы", default=1)

    class Meta:
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответа"

    def __str__(self):
        return self.text


class DiagOptionWeight(models.Model):
    option = models.ForeignKey(DiagOption, on_delete=models.CASCADE, related_name="weights", verbose_name="Ответ")
    scale = models.ForeignKey(DiagScale, on_delete=models.CASCADE, related_name="option_weights", verbose_name="Шкала")
    points = models.PositiveSmallIntegerField("Вес", default=1)

    class Meta:
        verbose_name = "Вес ответа по шкале"
        verbose_name_plural = "Веса ответа по шкалам"
        unique_together = [("option", "scale")]

    def clean(self):
        super().clean()
        if self.option_id and self.scale_id and self.option.question.test_id != self.scale.test_id:
            from django.core.exceptions import ValidationError

            raise ValidationError("Шкала должна относиться к той же диагностике, что и вопрос.")

    def __str__(self):
        return f"{self.option} · {self.scale}: {self.points}"


class DiagResult(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="diag_results", verbose_name="Студент")
    test = models.ForeignKey(DiagTest, on_delete=models.CASCADE, related_name="results", verbose_name="Тест")
    scores = models.JSONField("Профиль, % по шкалам", default=dict)
    recommended = models.ManyToManyField(Track, blank=True, verbose_name="Рекомендованные треки")
    created_at = models.DateTimeField("Пройдено", auto_now_add=True)

    class Meta:
        verbose_name = "Результат диагностики"
        verbose_name_plural = "Результаты диагностики"
        ordering = ["-created_at"]


# ---------- маршрут первокурсника ----------

class RouteStage(models.Model):
    class Condition(models.TextChoices):
        ACTIVITIES = "activities", "Посетить N мероприятий"
        DIAGNOSTIC = "diagnostic", "Пройти профдиагностику"
        TRACKS = "tracks", "Попробовать N треков (выполнить хотя бы одну активность в каждом)"
        MENTOR = "mentor", "Сходить на N встреч с наставником"
        EMPLOYERS = "employers", "Побывать у N разных работодателей"
        MAIN_TRACK = "main_track", "Выбрать основной трек"
        RESUME = "resume", "Заполнить резюме"
        PORTFOLIO = "portfolio", "Собрать N записей в портфолио"

    order = models.PositiveIntegerField("Порядок", default=0)
    title = models.CharField("Этап", max_length=100)
    description = models.CharField("Что сделать", max_length=255, blank=True)
    deadline = models.DateField("Срок", null=True, blank=True)

    class Meta:
        verbose_name = "Этап маршрута"
        verbose_name_plural = "Маршрут первокурсника"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class StageCondition(models.Model):
    stage = models.ForeignKey(RouteStage, on_delete=models.CASCADE, related_name="conditions", verbose_name="Этап")
    kind = models.CharField("Условие", max_length=12, choices=RouteStage.Condition.choices)
    count = models.PositiveIntegerField("N", default=1)

    class Meta:
        verbose_name = "Условие этапа"
        verbose_name_plural = "Условия этапа (должны выполниться все)"

    def __str__(self):
        return f"{self.get_kind_display()} ({self.count})"


# ---------- наставники ----------

class MentorSlot(models.Model):
    mentor = models.ForeignKey(U, on_delete=models.CASCADE, related_name="mentor_slots", verbose_name="Наставник")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="slots", verbose_name="Трек")
    topic = models.CharField("Тема встречи", max_length=150)
    start = models.DateTimeField("Начало")
    duration = models.PositiveIntegerField("Длительность, мин", default=45)
    place = models.CharField("Место или ссылка", max_length=200)
    capacity = models.PositiveIntegerField("Мест", default=5)
    is_cancelled = models.BooleanField("Отменена", default=False)
    held = models.BooleanField("Проведена", default=False)

    class Meta:
        verbose_name = "Встреча наставника"
        verbose_name_plural = "Встречи наставников"
        ordering = ["start"]

    def __str__(self):
        return f"{self.topic} — {self.mentor} ({timezone.localtime(self.start):%d.%m %H:%M})"

    def booked(self):
        return self.bookings.exclude(status=MentorBooking.Status.CANCELLED).count()

    @property
    def free(self):
        return max(self.capacity - self.booked(), 0)

    @property
    def is_past(self):
        return timezone.now() > self.start


class MentorBooking(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Записан"
        ATTENDED = "attended", "Был на встрече"
        MISSED = "missed", "Не пришёл"
        CANCELLED = "cancelled", "Отменил"

    slot = models.ForeignKey(MentorSlot, on_delete=models.CASCADE, related_name="bookings", verbose_name="Встреча")
    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="mentor_bookings", verbose_name="Первокурсник")
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.BOOKED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Запись на встречу"
        verbose_name_plural = "Записи на встречи"
        unique_together = [("slot", "user")]


# ---------- портфолио и резюме ----------

class ExternalAchievement(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        APPROVED = "approved", "Подтверждено"
        REJECTED = "rejected", "Отклонено"

    user = models.ForeignKey(U, on_delete=models.CASCADE, related_name="external_achievements", verbose_name="Студент")
    title = models.CharField("Достижение", max_length=200, help_text="Например, «Сертификат курса по Python»")
    issuer = models.CharField("Кто выдал", max_length=150, blank=True)
    date = models.DateField("Дата", null=True, blank=True)
    file = models.FileField("Файл (скан, фото)", upload_to="portfolio/%Y/%m/", storage=PrivatePortfolioStorage(), blank=True)
    url = models.URLField("Ссылка", blank=True)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.PENDING)
    comment = models.CharField("Комментарий проверяющего", max_length=255, blank=True)
    reviewed_by = models.ForeignKey(U, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Проверил")
    created_at = models.DateTimeField("Загружено", auto_now_add=True)

    class Meta:
        verbose_name = "Внешнее достижение"
        verbose_name_plural = "Внешние достижения"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


def gen_token():
    return secrets.token_urlsafe(12)


class Resume(models.Model):
    user = models.OneToOneField(U, on_delete=models.CASCADE, related_name="resume", verbose_name="Студент")
    headline = models.CharField("Кем хочу стать", max_length=120, blank=True)
    about = models.TextField("О себе", blank=True, max_length=1500)
    skills = models.CharField("Навыки", max_length=400, blank=True, help_text="Через запятую")
    contacts = models.CharField("Контакты для работодателя", max_length=200, blank=True, help_text="Телефон, e-mail или ник в мессенджере")
    show_diagnostic = models.BooleanField("Показывать результат профдиагностики", default=False)
    public = models.BooleanField("Открыть по ссылке", default=False)
    token = models.CharField(max_length=32, unique=True, default=gen_token)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Резюме"
        verbose_name_plural = "Резюме"

    @property
    def is_filled(self):
        return bool(self.headline and self.about and self.skills)

    def skill_list(self):
        return [s.strip() for s in self.skills.split(",") if s.strip()]


# ---------- велком-наборы и фонд одежды ----------

class FundItem(models.Model):
    class Kind(models.TextChoices):
        WELCOME = "welcome", "Велком-набор (выдаётся насовсем)"
        LOAN = "loan", "Фонд одежды (выдаётся на время)"

    name = models.CharField("Предмет", max_length=120)
    kind = models.CharField("Тип", max_length=10, choices=Kind.choices)
    stock = models.PositiveIntegerField("На складе", default=0)

    class Meta:
        verbose_name = "Предмет фонда"
        verbose_name_plural = "Велком-наборы и фонд одежды"

    def __str__(self):
        return self.name

    def on_hands(self):
        return self.issues.filter(returned_at__isnull=True).count() if self.kind == self.Kind.LOAN else 0


class FundIssue(models.Model):
    item = models.ForeignKey(FundItem, on_delete=models.PROTECT, related_name="issues", verbose_name="Предмет")
    user = models.ForeignKey(U, on_delete=models.PROTECT, related_name="fund_issues", verbose_name="Кому")
    size = models.CharField("Размер", max_length=10, blank=True)
    issued_at = models.DateTimeField("Выдано", default=timezone.now)
    issued_by = models.ForeignKey(U, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Выдал")
    returned_at = models.DateTimeField("Возвращено", null=True, blank=True)
    note = models.CharField("Примечание", max_length=200, blank=True, help_text="Состояние, стирка, ремонт")

    class Meta:
        verbose_name = "Выдача"
        verbose_name_plural = "Выдачи из фонда"
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.item} → {self.user}"
