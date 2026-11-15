from django.conf import settings
from django.db import models
from django.db.models import Q


class SiteSettings(models.Model):
    """Глобальные настройки (одна запись)."""

    currency_one = models.CharField("Валюта: 1 (степ)", max_length=30, default="степ")
    currency_few = models.CharField("Валюта: 2–4 (степа)", max_length=30, default="степа")
    currency_many = models.CharField("Валюта: 5+ (степов)", max_length=30, default="степов")
    currency_icon = models.CharField("Иконка валюты", max_length=8, default="✦")
    manual_credit_limit = models.PositiveIntegerField("Лимит одного ручного начисления", default=500)
    manual_daily_limit = models.PositiveIntegerField("Лимит ручных начислений администратора в сутки", default=2000)
    order_expire_days = models.PositiveIntegerField("Срок хранения невыданного заказа, дней", default=30)
    mentor_meeting_reward = models.PositiveIntegerField("Первокурснику за встречу с наставником", default=10)
    mentoring_reward = models.PositiveIntegerField("Наставнику за проведённую встречу", default=20)

    class Meta:
        verbose_name = verbose_name_plural = "Настройки платформы"

    def __str__(self):
        return "Настройки платформы"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def plural(self, n):
        n = abs(int(n))
        if n % 10 == 1 and n % 100 != 11:
            return self.currency_one
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return self.currency_few
        return self.currency_many


class Audience(models.Model):
    """Аудитория объекта: все студенты, либо выбранные курсы и/или группы."""

    for_all = models.BooleanField("Для всех студентов", default=True)
    courses = models.CharField(
        "Курсы", max_length=20, blank=True, help_text="Номера курсов через запятую, например: 1,2"
    )
    groups = models.ManyToManyField(
        "accounts.StudyGroup", blank=True, related_name="+", verbose_name="Группы"
    )

    class Meta:
        abstract = True

    @classmethod
    def audience_q(cls, user):
        if user.is_staff_role:
            return Q()
        q = Q(for_all=True)
        if user.group_id:
            q |= Q(groups=user.group_id)
            course = user.group.course
            q |= Q(courses=str(course)) | Q(courses__startswith=f"{course},") | Q(
                courses__endswith=f",{course}"
            ) | Q(courses__contains=f",{course},")
        return q

    @classmethod
    def visible_to(cls, user, qs=None):
        qs = qs if qs is not None else cls.objects.all()
        return qs.filter(cls.audience_q(user)).distinct()

    def is_visible_to(self, user):
        return type(self).visible_to(user, type(self).objects.filter(pk=self.pk)).exists()

    def audience_students(self):
        """Активные студенты из аудитории объекта."""
        from accounts.models import User

        students = User.objects.filter(role=User.Role.STUDENT, expelled=False, is_active=True)
        if self.for_all:
            return students
        courses = [int(c) for c in self.courses.split(",") if c.strip().isdigit()]
        return students.filter(Q(group__in=self.groups.all()) | Q(group__course__in=courses)).distinct()

    def audience_label(self):
        if self.for_all:
            return "Все студенты"
        parts = []
        if self.courses:
            parts.append("курсы " + self.courses)
        if self.pk:
            parts += [g.name for g in self.groups.all()]
        return ", ".join(parts) or "—"


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, verbose_name="Кто")
    action = models.CharField("Действие", max_length=100)
    target = models.CharField("Объект", max_length=255, blank=True)
    details = models.JSONField("Подробности", default=dict, blank=True)
    created_at = models.DateTimeField("Когда", auto_now_add=True)

    class Meta:
        verbose_name = "Запись журнала действий"
        verbose_name_plural = "Журнал действий"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%d.%m.%Y %H:%M} {self.actor} — {self.action}"

    @classmethod
    def log(cls, actor, action, target="", **details):
        return cls.objects.create(actor=actor, action=action, target=str(target)[:255], details=details)
