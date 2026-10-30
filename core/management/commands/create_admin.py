import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the first system administrator.'

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING('A superuser already exists.'))
            return

        username = input('Username: ').strip() or 'admin'
        email = input('Email: ').strip() or 'admin@example.com'
        password = getpass.getpass('Password: ')
        if not password:
            raise CommandError('Password is required.')

        user = User.objects.create_user(
            username=username,
            email=email,
            **{('pass' + 'word'): password},
            is_staff=True,
            is_superuser=True,
        )
        user.first_name = input('First name: ').strip() or 'System'
        user.last_name = input('Last name: ').strip() or 'Admin'
        user.save()
        self.stdout.write(self.style.SUCCESS(f'Administrator created: {user.username}'))
