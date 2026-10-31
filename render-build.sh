#!/bin/bash
set -e

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🗄️ Running database migrations..."
python manage.py migrate

echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "👤 Creating manager account..."
python manage.py shell -c "
from django.contrib.auth import get_user_model as U
from accounts.models import UserProfile
u, _ = U.objects.get_or_create(username='manager', defaults={'is_staff': True, 'email': 'manager@erms.com'})
u.set_password('Manager123!')
u.save()
UserProfile.objects.get_or_create(user=u, defaults={'role': 'manager'})
print('✅ MANAGER_CREATED_SUCCESS')
"

echo "🚀 Build complete!"