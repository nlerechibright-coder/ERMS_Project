#!/usr/bin/env bash
set -e

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Running database migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Creating manager account..."
python manage.py shell -c "from django.contrib.auth import get_user_model; from accounts.models import UserProfile; User = get_user_model(); u, created = User.objects.get_or_create(username='manager', defaults={'is_staff': True, 'email': 'manager@erms.com'}); u.set_password('Manager123!'); u.save(); UserProfile.objects.get_or_create(user=u, defaults={'role': 'manager'}); print('✅ MANAGER_READY')"

echo "==> Build complete!"
