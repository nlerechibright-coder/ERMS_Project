from decimal import Decimal

from django.conf import settings
from django.db import models


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Expense(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PAID', 'Paid'),
    ]

    title = models.CharField(max_length=200)
    category = models.ForeignKey('ExpenseCategory', on_delete=models.PROTECT, related_name='expenses', null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    expense_date = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_expenses')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses')
    payment_reference = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-expense_date', '-id']

    def __str__(self):
        return self.title


class PaymentEntry(models.Model):
    expense = models.ForeignKey('Expense', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f'{self.expense.title} - {self.amount}'
