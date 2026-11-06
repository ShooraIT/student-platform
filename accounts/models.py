from django.contrib.auth.models import AbstractUser
from django.db import models


class StudyGroup(models.Model):
    name = models.CharField("Название", max_length=50, unique=True)
    course = models.PositiveSmallIntegerField("Курс", default=1)
    specialty = models.CharField("Специальность", max_length=100, blank=True)

    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "Группы"
        ordering = ["course", "name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Студент"
        ADMIN = "admin", "Администратор"
        SUPERADMIN = "superadmin", "Суперадминистратор"

    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.STUDENT)
    group = models.ForeignKey(
        StudyGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="students", verbose_name="Группа"
    )
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    mesh_id = models.CharField("ID в МЭШ", max_length=100, null=True, blank=True, unique=True)
    balance = models.PositiveIntegerField("Баланс", default=0, editable=False)
    must_change_password = models.BooleanField("Сменить пароль при входе", default=False)
    hide_from_rating = models.BooleanField("Скрыть из рейтинга", default=False)
    expelled = models.BooleanField("Выбыл", default=False)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name or self.username

    @property
    def full_name(self):
        return " ".join(p for p in [self.last_name, self.first_name, self.middle_name] if p)

    @property
    def short_name(self):
        return f"{self.first_name} {self.last_name[:1]}.".strip() if self.last_name else self.first_name

    @property
    def is_staff_role(self):
        return self.role in (self.Role.ADMIN, self.Role.SUPERADMIN) or self.is_superuser

    @property
    def is_student(self):
        return not self.is_staff_role

    def save(self, *args, **kwargs):
        # Администраторы получают доступ к админ-панели Django
        if self.role in (self.Role.ADMIN, self.Role.SUPERADMIN):
            self.is_staff = True
        if self.role == self.Role.SUPERADMIN:
            self.is_superuser = True
        if self.expelled:
            self.is_active = False
        super().save(*args, **kwargs)


class UnmatchedMeshLogin(models.Model):
    """Вход через МЭШ, который не удалось сопоставить со студентом из импорта (п. 3.3 ТЗ)."""

    mesh_id = models.CharField("ID в МЭШ", max_length=100, unique=True)
    last_name = models.CharField("Фамилия", max_length=150, blank=True)
    first_name = models.CharField("Имя", max_length=150, blank=True)
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    email = models.CharField("E-mail", max_length=254, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    raw = models.JSONField("Данные МЭШ", default=dict)
    candidates = models.ManyToManyField(User, blank=True, verbose_name="Возможные совпадения")
    linked_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Привязать к студенту"
    )
    created_at = models.DateTimeField("Первая попытка", auto_now_add=True)

    class Meta:
        verbose_name = "Несопоставленный вход МЭШ"
        verbose_name_plural = "Несопоставленные входы МЭШ"

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.mesh_id})"
