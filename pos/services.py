import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from .models import DailySalesSubmission, DailySubmissionEvent, PosReceipt, PosReceiptItem
from .utils import business_today

MONEY = Decimal("0.01")
QTY = Decimal("0.001")


def _money(value):
    return (value or Decimal("0")).quantize(MONEY)


def _qty(value):
    return (value or Decimal("0")).quantize(QTY)


def receipts_for_user_date(user, date):
    return PosReceipt.objects.filter(
        staff_user=user,
        business_date=date,
        status="COMPLETED",
    )


def receipts_for_date(date):
    return PosReceipt.objects.filter(
        business_date=date,
        status="COMPLETED",
    )


def summarize_receipts(receipts):
    receipt_ids = list(receipts.values_list("id", flat=True))
    items = PosReceiptItem.objects.filter(receipt_id__in=receipt_ids)

    receipt_agg = receipts.aggregate(
        sales_total=Sum("grand_total"),
        payment_total=Sum("amount_tendered"),
    )

    item_agg = items.aggregate(
        item_quantity_total=Sum("stock_quantity_deducted"),
    )

    by_product = list(
        items.values(
            "product_id",
            "product__name",
            "product__sku",
            "product__stock_unit",
        )
        .annotate(
            quantity=Sum("stock_quantity_deducted"),
            amount=Sum("line_total"),
        )
        .order_by("-amount")
    )

    for row in by_product:
        row["product_name"] = row.pop("product__name")
        row["sku"] = row.pop("product__sku")
        row["stock_unit"] = row.pop("product__stock_unit")
        row["quantity"] = _qty(row["quantity"])
        row["amount"] = _money(row["amount"])

    by_category = list(
        items.values("product__category__name")
        .annotate(
            quantity=Sum("stock_quantity_deducted"),
            amount=Sum("line_total"),
        )
        .order_by("-amount")
    )

    for row in by_category:
        row["category"] = row.pop("product__category__name") or "Uncategorized"
        row["quantity"] = _qty(row["quantity"])
        row["amount"] = _money(row["amount"])

    payment_methods = dict(PosReceipt.PAYMENT_METHOD_CHOICES)
    payment_breakdown = list(
        receipts.values("payment_method")
        .annotate(
            amount=Sum("grand_total"),
            tendered=Sum("amount_tendered"),
        )
        .order_by("payment_method")
    )

    for row in payment_breakdown:
        row["method_display"] = payment_methods.get(row["payment_method"], row["payment_method"])
        row["amount"] = _money(row["amount"])
        row["tendered"] = _money(row["tendered"])

    return {
        "transaction_count": receipts.count(),
        "sales_total": _money(receipt_agg["sales_total"]),
        "payment_total": _money(receipt_agg["payment_total"]),
        "item_quantity_total": _qty(item_agg["item_quantity_total"]),
        "by_product": by_product,
        "by_category": by_category,
        "payment_breakdown": payment_breakdown,
    }


def compute_daily_summary(user, date=None):
    date = date or business_today()
    return summarize_receipts(receipts_for_user_date(user, date))


def compute_date_summary(date=None):
    date = date or business_today()
    receipts = receipts_for_date(date)
    summary = summarize_receipts(receipts)

    by_salesperson = []
    rows = receipts.values(
        "staff_user_id",
        "staff_user__username",
    ).annotate(
        transactions=Count("id"),
        sales_total=Sum("grand_total"),
    ).order_by("-sales_total")

    for row in rows:
        qty = PosReceiptItem.objects.filter(
            receipt__staff_user_id=row["staff_user_id"],
            receipt__business_date=date,
            receipt__status="COMPLETED",
        ).aggregate(total=Sum("stock_quantity_deducted"))["total"]

        row["quantity"] = _qty(qty)
        row["sales_total"] = _money(row["sales_total"])
        by_salesperson.append(row)

    summary["by_salesperson"] = by_salesperson
    return summary


def submit_daily_sales_service(user, date=None):
    date = date or business_today()

    with transaction.atomic():
        active = DailySalesSubmission.objects.filter(
            staff_user=user,
            business_date=date,
        ).exclude(
            status="REJECTED",
        ).order_by("-created_at").first()

        if active:
            raise ValidationError(
                "You have already submitted your daily sales for this date."
            )

        submission = DailySalesSubmission.objects.filter(
            staff_user=user,
            business_date=date,
            status="REJECTED",
        ).order_by("-created_at").first()

        receipts = receipts_for_user_date(user, date)
        if not receipts.exists():
            raise ValidationError("No completed sales found for today.")

        summary = summarize_receipts(receipts)
        if summary["transaction_count"] == 0:
            raise ValidationError("No completed sales found for today.")

        is_new = submission is None

        if is_new:
            reference = f"DS-{user.username}-{date.strftime('%Y%m%d')}"
            if DailySalesSubmission.objects.filter(reference=reference).exists():
                reference = f"{reference}-{uuid.uuid4().hex[:6].upper()}"

            submission = DailySalesSubmission.objects.create(
                reference=reference,
                staff_user=user,
                business_date=date,
                status="SUBMITTED",
                transaction_count=summary["transaction_count"],
                item_quantity_total=summary["item_quantity_total"],
                sales_total=summary["sales_total"],
                payment_total=summary["payment_total"],
                submitted_at=timezone.now(),
            )

            action = "SUBMITTED"
            message = "Daily sales submitted."
        else:
            old_reason = submission.rejection_reason

            submission.status = "SUBMITTED"
            submission.transaction_count = summary["transaction_count"]
            submission.item_quantity_total = summary["item_quantity_total"]
            submission.sales_total = summary["sales_total"]
            submission.payment_total = summary["payment_total"]
            submission.submitted_at = timezone.now()
            submission.reviewed_by = None
            submission.reviewed_at = None
            submission.rejection_reason = ""

            submission.save(update_fields=[
                "status",
                "transaction_count",
                "item_quantity_total",
                "sales_total",
                "payment_total",
                "submitted_at",
                "reviewed_by",
                "reviewed_at",
                "rejection_reason",
            ])

            action = "RESUBMITTED"
            if old_reason:
                message = f"Resubmitted after rejection. Previous reason: {old_reason}"
            else:
                message = "Resubmitted."

        receipts.update(daily_submission=submission)

        DailySubmissionEvent.objects.create(
            submission=submission,
            action=action,
            user=user,
            message=message,
        )

        return submission


def accept_submission(submission, manager):
    with transaction.atomic():
        if submission.status == "ACCEPTED":
            raise ValidationError("This submission has already been accepted.")

        if submission.status == "REJECTED":
            raise ValidationError(
                "A rejected submission cannot be accepted. The staff member must resubmit."
            )

        if submission.status not in ("SUBMITTED", "UNDER_REVIEW"):
            raise ValidationError("Only submitted or under-review submissions can be accepted.")

        submission.status = "ACCEPTED"
        submission.reviewed_by = manager
        submission.reviewed_at = timezone.now()
        submission.rejection_reason = ""
        submission.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
        ])

        DailySubmissionEvent.objects.create(
            submission=submission,
            action="ACCEPTED",
            user=manager,
            message="Submission accepted by manager.",
        )

        return submission


def reject_submission(submission, manager, reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("A rejection reason is required.")

    with transaction.atomic():
        if submission.status == "ACCEPTED":
            raise ValidationError("An accepted submission cannot be rejected.")

        if submission.status == "REJECTED":
            raise ValidationError("This submission has already been rejected.")

        if submission.status not in ("SUBMITTED", "UNDER_REVIEW"):
            raise ValidationError("Only submitted or under-review submissions can be rejected.")

        submission.status = "REJECTED"
        submission.reviewed_by = manager
        submission.reviewed_at = timezone.now()
        submission.rejection_reason = reason
        submission.save(update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
        ])

        DailySubmissionEvent.objects.create(
            submission=submission,
            action="REJECTED",
            user=manager,
            message=reason,
        )

        return submission
