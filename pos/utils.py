from datetime import datetime
from zoneinfo import ZoneInfo

from django.utils import timezone

BUSINESS_TZ = ZoneInfo("Africa/Lagos")


def business_now():
    return datetime.now(BUSINESS_TZ)


def business_today():
    return business_now().date()


def business_date_of(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.astimezone(BUSINESS_TZ).date()
