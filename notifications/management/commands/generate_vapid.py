from django.core.management.base import BaseCommand

from notifications.vapid import generate


class Command(BaseCommand):
    help = "Сгенерировать VAPID-ключи для Web Push и вывести строки для .env"

    def handle(self, *args, **opts):
        k = generate()
        self.stdout.write(f"VAPID_PUBLIC_KEY={k['public']}\nVAPID_PRIVATE_KEY={k['private']}")
        self.stdout.write("Важно: после смены ключей все студенты должны заново включить пуш-уведомления.")
