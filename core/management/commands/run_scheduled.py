"""Периодические задачи. Запускать по cron каждые 5 минут:  python manage.py run_scheduled"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from events.models import Event, Registration
from notifications.models import Notification
from notifications.services import notify
from shop.services import expire_old_orders


class Command(BaseCommand):
    help = "Напоминания о мероприятиях и отмена невыданных заказов"

    def handle(self, *args, **opts):

        reminders = self.remind()
        expired = expire_old_orders()
        self.stdout.write(f"Напоминаний: {reminders}; заказов отменено: {expired}")

    def remind(self):
        now = timezone.now()
        sent = 0
        for hours, label in ((24, "завтра"), (1, "через час")):
            window = Event.objects.filter(
                status=Event.Status.PUBLISHED, start__gt=now + timedelta(hours=hours) - timedelta(minutes=10),
                start__lte=now + timedelta(hours=hours),
            )
            for e in window:
                url = f"/events/{e.pk}/"
                text = f"Напоминание: «{e.title}» {label}, {timezone.localtime(e.start):%H:%M}, {e.location}"
                for r in e.registrations.filter(status=Registration.Status.REGISTERED).select_related("user"):
                    if not Notification.objects.filter(user=r.user, url=url, text=text).exists():
                        notify(r.user, text, url, "reminder")
                        sent += 1
        return sent
