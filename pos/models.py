from django.conf import settings
from django.db import models

from inventory.models import Product

from .utils import business_today


class DailySalesSubmission(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("UNDER_REVIEW", "Under Review"),
        ("ACCEPTED", "Accepted"),
        ("REJECTED", "Rejected"),
    ]

    reference = models.CharField(max_length=60, unique=True)
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="daily_submissions",
    )
    business_date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    transaction_count = models.PositiveIntegerField(default=0)
    item_quantity_total = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    sales_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    payment_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_daily_submissions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-business_date", "-created_at"]

    def __str__(self):
        return f"{self.reference} {self.staff_user.username} {self.business_date}"


class DailySubmissionEvent(models.Model):
    ACTION_CHOICES = [
        ("CREATED", "Created"),
        ("SUBMITTED", "Submitted"),
        ("RESUBMITTED", "Resubmitted"),
        ("ACCEPTED", "Accepted"),
        ("REJECTED", "Rejected"),
    ]

    submission = models.ForeignKey(
        DailySalesSubmission,
        on_delete=models.CASCADE,
        related_name="events",
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="daily_submission_events",
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.submission.reference} {self.action}"


class PosReceipt(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("TRANSFER", "Transfer"),
        ("POS_TERMINAL", "POS Terminal"),
    ]

    STATUS_CHOICES = [
        ("COMPLETED", "Completed"),
        ("VOIDED", "Voided"),
    ]

    reference = models.CharField(max_length=60, unique=True)
    staff_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pos_receipts",
    )
    staff_username = models.CharField(max_length=150, blank=True, default="")
    business_date = models.DateField(default=business_today, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount_tendered = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    change_due = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="CASH",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED")

    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    daily_submission = models.ForeignKey(
        DailySalesSubmission,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="receipts",
    )

    void_reason = models.TextField(blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voided_pos_receipts",
    )
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class PosReceiptItem(models.Model):
    SALE_UNIT_CHOICES = [
        ("stock", "Stock unit"),
        ("purchase", "Purchase unit"),
    ]

    receipt = models.ForeignKey(PosReceipt, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="pos_items")

    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=60)
    stock_unit = models.CharField(max_length=20)

    sale_unit = models.CharField(max_length=20, choices=SALE_UNIT_CHOICES, default="stock")
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    conversion_factor = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    stock_quantity_deducted = models.DecimalField(max_digits=12, decimal_places=3)

    cost_basis_per_unit = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    cost_basis_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gross_profit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost_is_known = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.receipt.reference} {self.product_name}"
