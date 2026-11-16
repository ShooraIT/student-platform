import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import StudyGroup


class Command(BaseCommand):
    help = "Синхронизировать учебные группы с актуальным реестром БУП"

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(__file__).resolve().parents[2] / "data" / "study_groups_2026_2027.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        names = [row["name"] for row in payload["groups"]]
        archived = StudyGroup.objects.exclude(name__in=names).update(is_active=False)
        created = updated = 0
        for row in payload["groups"]:
            group, was_created = StudyGroup.objects.update_or_create(
                name=row["name"],
                defaults={
                    "course": row["course"],
                    "specialty": row["specialty"],
                    "specialty_name": row["specialty_name"],
                    "is_active": True,
                },
            )
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(
            f"Реестр {payload['academic_year']}: {created} групп добавлено, {updated} обновлено; "
            f"{archived} прежних групп отмечено архивными без удаления."
        ))
