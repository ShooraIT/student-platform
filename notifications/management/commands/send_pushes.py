import time

from django.core.management.base import BaseCommand

from notifications.services import push_configured, send_pending


class Command(BaseCommand):
    help = "Отправить пуш-уведомления из очереди. С --loop работает постоянно (для сервиса scheduler)"

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=10)

    def handle(self, *args, **opts):
        if not push_configured():
            self.stderr.write("VAPID-ключи не заданы — пуши отключены")
            return
        while True:
            n = send_pending()
            if not opts["loop"]:
                self.stdout.write(f"Отправлено: {n}")
                return
            time.sleep(opts["interval"])
