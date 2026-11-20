import os

from django.core.management.base import BaseCommand

from core.models import User


class Command(BaseCommand):
    help = "Create the superuser from SUPERUSER_EMAIL / SUPERUSER_PASSWORD if it does not exist."

    def handle(self, *args, **options):
        email = (os.environ.get("SUPERUSER_EMAIL") or "").strip().lower()
        password = os.environ.get("SUPERUSER_PASSWORD") or ""

        if not email or not password:
            self.stdout.write(
                "SUPERUSER_EMAIL / SUPERUSER_PASSWORD not set , skipping superuser creation."
            )
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(f"Superuser {email} already exists.")
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser {email}."))
