"""Импорт студентов из Excel (п. 3.3 ТЗ)."""
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime

from django.db import transaction
from openpyxl import Workbook, load_workbook

from .models import StudyGroup, User

COLUMNS = ["Фамилия", "Имя", "Отчество", "Группа", "Курс", "Специальность", "E-mail / логин mos.ru", "Дата рождения"]
PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
     "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"],
))


def translit(s):
    return "".join(TRANSLIT.get(c, c) for c in s.lower() if c.isalnum())


def gen_password():
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(8))


def template_workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = "Студенты"
    ws.append(COLUMNS)
    ws.append(["Иванова", "Мария", "Сергеевна", "СИП-21", 2, "09.02.07", "ivanova@mail.ru", "12.03.2008"])
    for col, w in zip("ABCDEFGH", [16, 14, 16, 10, 6, 14, 26, 14]):
        ws.column_dimensions[col].width = w
    return wb


@dataclass
class Row:
    line: int
    last_name: str
    first_name: str
    middle_name: str
    group: str
    course: int
    specialty: str
    email: str
    birth_date: date | None
    user: User | None = None


@dataclass
class ImportPlan:
    rows: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def to_create(self):
        return [r for r in self.rows if r.user is None]

    @property
    def to_update(self):
        return [r for r in self.rows if r.user is not None]


def _cell(v):
    return "" if v is None else str(v).strip()


def _parse_date(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"не удалось разобрать дату «{v}»")


def find_existing(r):
    if r.email:
        u = User.objects.filter(email__iexact=r.email).first()
        if u:
            return u
    qs = User.objects.filter(
        last_name__iexact=r.last_name, first_name__iexact=r.first_name, middle_name__iexact=r.middle_name
    )
    if r.birth_date:
        u = qs.filter(birth_date=r.birth_date).first()
        if u:
            return u
    qs = qs.filter(group__name=r.group)
    return qs.first() if qs.count() == 1 else None


def parse(file):
    plan = ImportPlan()
    wb = load_workbook(file, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [_cell(c) for c in next(rows, [])]
    idx = {}
    for i, name in enumerate(header):
        for col in COLUMNS:
            if name.lower().startswith(col.lower()[:6]):
                idx.setdefault(col, i)
    missing = [c for c in ("Фамилия", "Имя", "Группа", "Курс") if c not in idx]
    if missing:
        plan.errors.append((1, "Нет обязательных колонок: " + ", ".join(missing)))
        return plan
    get = lambda row, col: _cell(row[idx[col]]) if col in idx and idx[col] < len(row) else ""  # noqa: E731
    for line, row in enumerate(rows, start=2):
        if not any(row):
            continue
        try:
            last, first, grp = get(row, "Фамилия"), get(row, "Имя"), get(row, "Группа")
            if not (last and first and grp):
                raise ValueError("не заполнены фамилия, имя или группа")
            course = int(float(get(row, "Курс") or 0))
            if not 1 <= course <= 6:
                raise ValueError("курс должен быть числом от 1 до 6")
            r = Row(
                line, last, first, get(row, "Отчество"), grp, course, get(row, "Специальность"),
                get(row, "E-mail / логин mos.ru"), _parse_date(row[idx["Дата рождения"]] if "Дата рождения" in idx else None),
            )
        except ValueError as e:
            plan.errors.append((line, str(e)))
            continue
        r.user = find_existing(r)
        plan.rows.append(r)
    return plan


def _unique_username(r):
    base = translit(r.last_name) + "." + translit(r.first_name)[:1]
    name, n = base, 1
    while User.objects.filter(username=name).exists():
        n += 1
        name = f"{base}{n}"
    return name


@transaction.atomic
def apply(plan, mark_missing_expelled=False):
    """Создаёт и обновляет студентов. Возвращает список (студент, одноразовый пароль) для новых."""
    credentials = []
    seen = set()
    groups = {}
    for r in plan.rows:
        g = groups.get(r.group)
        if g is None:
            g, _ = StudyGroup.objects.get_or_create(
                name=r.group,
                defaults={"course": r.course, "specialty": r.specialty, "is_active": r.course == 1},
            )
            if g.course != r.course or (r.specialty and g.specialty != r.specialty) or g.is_active != (r.course == 1):
                g.course, g.specialty = r.course, r.specialty or g.specialty
                g.is_active = r.course == 1
                g.save()
            groups[r.group] = g
        u = r.user
        if u is None:
            u = User(username=_unique_username(r), role=User.Role.STUDENT, must_change_password=True)
            pwd = gen_password()
            u.set_password(pwd)
            credentials.append((u, pwd))
        u.last_name, u.first_name, u.middle_name = r.last_name, r.first_name, r.middle_name
        u.group = g
        if r.email:
            u.email = r.email
        if r.birth_date:
            u.birth_date = r.birth_date
        u.expelled, u.is_active = False, True
        u.save()
        seen.add(u.pk)
    expelled = 0
    if mark_missing_expelled:
        for u in User.objects.filter(role=User.Role.STUDENT, expelled=False).exclude(pk__in=seen):
            u.expelled = True
            u.save()
            expelled += 1
    return credentials, expelled


def credentials_workbook(credentials):
    wb = Workbook()
    ws = wb.active
    ws.title = "Доступы"
    ws.append(["Группа", "ФИО", "Логин", "Одноразовый пароль"])
    for u, pwd in sorted(credentials, key=lambda c: (c[0].group.name if c[0].group else "", c[0].full_name)):
        ws.append([u.group.name if u.group else "", u.full_name, u.username, pwd])
    for col, w in zip("ABCD", [10, 36, 20, 20]):
        ws.column_dimensions[col].width = w
    return wb


def reset_password(user):
    pwd = gen_password()
    user.set_password(pwd)
    user.must_change_password = True
    user.save()
    return pwd
