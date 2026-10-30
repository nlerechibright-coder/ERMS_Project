from decimal import Decimal

from django.conf import settings
from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('CONFIRMED', 'Confirmed'),
        ('FULFILLED', 'Fulfilled'),
        ('CANCELLED', 'Cancelled'),
    ]

    customer = models.ForeignKey('Customer', on_delete=models.PROTECT, related_name='sales_orders')
    order_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    order_date = models.DateField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_sales_orders')
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_sales_orders')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-order_date', '-id']

    def __str__(self):
        return self.order_number

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.line_items.all())

    def recalculate_total(self):
        self.total_amount = sum((item.quantity * item.unit_price) for item in self.line_items.all())
        self.save(update_fields=['total_amount'])


class SalesOrderLineItem(models.Model):
    sales_order = models.ForeignKey('SalesOrder', on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey('inventory.Product', on_delete=models.PROTECT, related_name='sales_order_lines')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f'{self.sales_order.order_number} - {self.product.name}'
