from django.db import models


class ReportSnapshot(models.Model):
    title = models.CharField(max_length=200)
    generated_at = models.DateTimeField(auto_now_add=True)
    payload = models.TextField(blank=True)

    def __str__(self):
        return self.title
