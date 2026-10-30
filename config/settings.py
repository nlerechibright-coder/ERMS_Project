import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECRET KEY - from environment or fallback (insecure, for local dev only)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-erms-demo-key-change-in-production')

# DEBUG - from environment, default True for local development
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# ALLOWED HOSTS - from environment or sensible defaults
allowed_hosts = os.environ.get('ALLOWED_HOSTS', '')
if allowed_hosts:
    ALLOWED_HOSTS = allowed_hosts.split(',')
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.railway.app', '.up.railway.app']

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bootstrap5',
    'core',
    'accounts',
    'organization',
    'inventory',
    'procurement',
    'sales',
    'projects',
    'finance',
    'reports',
    'pos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# DATABASE CONFIGURATION
# Use PostgreSQL if DATABASE_URL is set (Railway), otherwise SQLite (local)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Parse DATABASE_URL for PostgreSQL
    import re
    match = re.match(r'postgres://([^:]+):([^@]+)@([^/]+)/(.+)', DATABASE_URL)
    if match:
        user, password, host_port, dbname = match.groups()
        host, port = host_port.split(':')
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': dbname,
                'USER': user,
                'PASSWORD': password,
                'HOST': host,
                'PORT': port,
            }
        }
    else:
        # Fallback: try dj_database_url style parsing
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': os.environ.get('PGDATABASE', 'railway'),
                'USER': os.environ.get('PGUSER', 'postgres'),
                'PASSWORD': os.environ.get('PGPASSWORD', ''),
                'HOST': os.environ.get('PGHOST', 'localhost'),
                'PORT': os.environ.get('PGPORT', '5432'),
            }
        }
else:
    # Local development: use SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static'] if (BASE_DIR / 'static').exists() else []

# WhiteNoise configuration for static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = 'DENY'

# CSRF settings for Railway
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.up.railway.app',
]

# Trust proxy SSL header (Railway uses HTTPS termination)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Login/Logout URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
