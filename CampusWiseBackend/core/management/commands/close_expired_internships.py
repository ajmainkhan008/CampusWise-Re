from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Internship, InternshipReviewLog


class Command(BaseCommand):
    help = "Automatically mark open internships with passed application deadlines as closed (FR-34)"

    def handle(self, *args, **options):
        today = timezone.now().date()
        expired_internships = Internship.objects.filter(
            status='open',
            application_deadline__lt=today
        )

        count = expired_internships.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"No expired internships found as of {today}."))
            return

        updated_count = expired_internships.update(status='closed', updated_at=timezone.now())
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully marked {updated_count} expired internship(s) as closed as of {today}."
            )
        )
