"""Статическая демо-витрина экранов студента для GitVerse Pages / любого статического хостинга.

    python manage.py export_demo --out ../stepy-demo --base /stepy-demo --user student1

Рендерит страницы под демо-студентом, переписывает ссылки под подпуть сайта,
отключает формы (в демо ничего не сохраняется) и копирует статику.
Запускать только на демо-базе (seed_demo): в витрину попадают реальные данные базы.
"""
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.test.utils import override_settings

from accounts.models import User
from assignments.models import Task
from events.models import Event
from shop.models import Order, Product
from surveys.models import Survey
from career.models import DiagTest, Employer, Track

DEMO_SNIPPET = """
<div style="background:#1d1f27;color:#fff;text-align:center;font:600 13px/1.4 Inter,system-ui,sans-serif;padding:8px 12px">
  ✦ Демо-версия платформы 01:17 · данные вымышленные · кнопки и формы не сохраняют изменения
</div>
<script>
document.addEventListener("submit", function (e) {
  e.preventDefault();
  alert("Это демо-версия: действия не сохраняются. В рабочей платформе здесь выполнится действие.");
}, true);
</script>
"""


class Command(BaseCommand):
    help = "Экспорт статической демо-версии экранов студента"

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="Папка, куда сохранить сайт")
        parser.add_argument("--base", default="", help="Подпуть сайта, например /stepy-demo")
        parser.add_argument("--user", default="student1", help="Логин демо-студента")

    def handle(self, *args, **o):
        out = Path(o["out"]).resolve()
        base = o["base"].rstrip("/")
        user = User.objects.filter(username=o["user"]).first()
        if not user or not user.is_student:
            raise CommandError("Нет такого студента. Сначала выполните seed_demo")

        pages = self.collect_pages(user)
        # Адрес страницы -> файл. Страницы с параметрами получают свои папки.
        route = {url: self.file_for(url) for url in pages}

        if out.exists():
            for child in out.iterdir():
                if child.name != ".git":
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
        out.mkdir(parents=True, exist_ok=True)

        with override_settings(ALLOWED_HOSTS=["*"], DEBUG=True):
            client = Client()
            client.force_login(user)
            ok = 0
            for url in pages:
                r = client.get(url)
                if r.status_code != 200:
                    self.stderr.write(f"пропуск {url}: {r.status_code}")
                    continue
                html = self.rewrite(r.content.decode(), route, base)
                path = out / route[url]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(html, encoding="utf-8")
                ok += 1

        shutil.copytree(Path(settings.BASE_DIR) / "static", out / "static")
        (out / ".nojekyll").write_text("")
        (out / "README.md").write_text(
            "# 01:17 — демо-версия\n\nСтатическая витрина экранов студента. "
            "Данные вымышленные, формы не работают. Исходный код — в ветке develop этого репозитория.\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(f"Готово: {ok} страниц в {out}"))

    def collect_pages(self, user):
        pages = [
            "/", "/events/", "/events/?view=month", "/tasks/", "/surveys/", "/shop/",
            "/rating/", "/rating/?period=semester", "/rating/?period=year", "/rating/?period=all",
            "/rating/groups/", "/rating/badges/", "/profile/", "/notifications/", "/notifications/settings/",
            "/career/", "/career/tracks/", "/career/meetings/", "/career/employers/",
            "/portfolio/", "/portfolio/resume/",
        ]
        pages += [f"/career/tracks/{t.slug}/" for t in Track.objects.filter(is_active=True)]
        test = DiagTest.objects.filter(is_active=True).order_by("id").first()
        if test:
            pages.append(f"/career/diagnostic/{test.pk}/")
        pages += [f"/career/employers/{e.pk}/" for e in Employer.objects.filter(is_active=True)]
        pages += [f"/events/{e.pk}/" for e in Event.visible_to(user, Event.objects.exclude(status=Event.Status.DRAFT))]
        pages += [f"/tasks/{t.pk}/" for t in Task.visible_to(user, Task.objects.filter(status=Task.Status.PUBLISHED))]
        pages += [f"/surveys/{s.pk}/" for s in Survey.visible_to(user, Survey.objects.filter(status=Survey.Status.PUBLISHED))]
        pages += [f"/shop/{p.pk}/" for p in Product.objects.filter(status=Product.Status.ON_SALE)]
        pages += [f"/shop/orders/{o.pk}/" for o in Order.objects.filter(user=user)]
        return list(dict.fromkeys(pages))

    @staticmethod
    def file_for(url):
        parts = urlsplit(url)
        path = parts.path.strip("/")
        if parts.query:
            path = (path + "/" if path else "") + re.sub(r"[^a-z0-9]+", "-", parts.query.lower()).strip("-")
        return (path + "/" if path else "") + "index.html"

    def rewrite(self, html, route, base):
        def link(m):
            attr, url = m.group(1), m.group(2)
            if url.startswith("/static/"):
                return f'{attr}="{base}{url}"'
            key = url.split("#")[0]
            anchor = url[len(key):]
            if key in route:
                target = route[key]
            else:
                # ссылки, которых нет в витрине: без параметров, если такая страница есть; иначе на главную
                bare = urlsplit(key).path
                target = route.get(bare, "index.html")
            target = target[: -len("index.html")]
            return f'{attr}="{base}/{target}{anchor}"'

        html = re.sub(r'(href|src|action)="(/[^"]*)"', link, html)
        # service worker и пуши в статике не работают
        html = re.sub(r"<script>if \(\"serviceWorker\".*?</script>", "", html, flags=re.S)
        html = html.replace('<link rel="manifest"', '<link rel="x-manifest"')
        html = html.replace("<body>", "<body>" + DEMO_SNIPPET, 1)
        return re.sub(r"[ \t]+(?=\r?$)", "", html, flags=re.M)
