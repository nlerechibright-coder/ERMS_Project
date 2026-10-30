from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('PARTIALLY_RECEIVED', 'Partially Received'),
        ('RECEIVED', 'Received'),
        ('CANCELLED', 'Cancelled'),
    ]

    supplier = models.ForeignKey('Supplier', on_delete=models.PROTECT, related_name='purchase_orders')
    order_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='DRAFT')
    order_date = models.DateField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_purchase_orders')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_purchase_orders')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-order_date', '-id']

    def __str__(self):
        return self.order_number

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.line_items.all())

    @property
    def received_quantity(self):
        return sum(item.received_quantity for item in self.line_items.all())

    @property
    def outstanding_quantity(self):
        return sum(item.outstanding_quantity for item in self.line_items.all())

    def recalculate_total(self):
        self.total_amount = sum((item.quantity * item.unit_price) for item in self.line_items.all())
        self.save(update_fields=['total_amount'])


class PurchaseOrderLineItem(models.Model):
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey('inventory.Product', on_delete=models.PROTECT, related_name='purchase_order_lines')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    received_quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.purchase_order.order_number} - {self.product.name}'

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    @property
    def outstanding_quantity(self):
        return max(self.quantity - self.received_quantity, 0)

    def clean(self):
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be greater than zero.'})


class GoodsReceipt(models.Model):
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.CASCADE, related_name='goods_receipts')
    receipt_number = models.CharField(max_length=60, unique=True)
    received_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='goods_receipts')

    class Meta:
        ordering = ['-received_date', '-id']

    def __str__(self):
        return self.receipt_number


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey('GoodsReceipt', on_delete=models.CASCADE, related_name='lines')
    line_item = models.ForeignKey('PurchaseOrderLineItem', on_delete=models.PROTECT, related_name='receipt_lines')
    quantity_received = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['line_item', 'receipt'], name='unique_receipt_line_item')
        ]

    def __str__(self):
        return f'{self.receipt.receipt_number} - {self.line_item.product.name}'
