from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=50, default='manager')
    phone = models.CharField(max_length=30, blank=True)
    department = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
