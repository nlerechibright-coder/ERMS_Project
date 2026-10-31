import datetime
import uuid
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.decorators import management_required, pos_access_required
from inventory.models import Product, StockMovement

from .models import DailySalesSubmission, PosReceipt, PosReceiptItem
from .services import (
    accept_submission,
    compute_daily_summary,
    compute_date_summary,
    reject_submission,
    summarize_receipts,
    submit_daily_sales_service,
)
from .utils import business_today

CART_KEY = "pos_cart"
CHECKOUT_KEY_SESSION = "pos_checkout_key"
TWO = Decimal("0.01")
THREE = Decimal("0.001")


def _dec(value, default="0"):
    try:
        return Decimal(str(value).strip() or default)
    except (InvalidOperation, AttributeError):
        return Decimal(default)


def _cart(request):
    return request.session.get(CART_KEY, []) or []


def _save_cart(request, cart):
    request.session[CART_KEY] = cart


def _clear_cart(request):
    request.session.pop(CART_KEY, None)
    request.session.pop(CHECKOUT_KEY_SESSION, None)


def _find_cart_index(cart, product_id, sale_unit):
    for i, item in enumerate(cart):
        try:
            pid = int(item.get("product_id"))
        except (TypeError, ValueError):
            continue
        if pid == int(product_id) and item.get("sale_unit", "stock") == sale_unit:
            return i
    return -1


def _search_products(q):
    base = Product.objects.filter(is_active=True, unit_price__gt=0).select_related("category")
    q = (q or "").strip()

    if not q:
        return list(base.order_by("name")[:20]), False

    lookup = (
        Q(name__icontains=q)
        | Q(sku__icontains=q)
        | Q(barcode__icontains=q)
        | Q(brand__icontains=q)
        | Q(category__name__icontains=q)
    )
    results = list(base.filter(lookup).order_by("name")[:20])
    if results:
        return results, False

    candidates = list(base.order_by("name")[:500])
    ql = q.lower()
    scored = []

    for product in candidates:
        text_parts = [
            product.name or "",
            product.sku or "",
            product.brand or "",
            product.category.name if product.category else "",
        ]
        text = " ".join([p for p in text_parts if p]).lower()
        ratio = SequenceMatcher(None, ql, text).ratio()

        for word in text.split():
            word_ratio = SequenceMatcher(None, ql, word).ratio()
            if word_ratio > ratio:
                ratio = word_ratio

        if ratio >= 0.45:
            scored.append((ratio, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [product for _, product in scored[:10]], True


def _build_lines(cart):
    ids = []
    for item in cart:
        try:
            ids.append(int(item.get("product_id")))
        except (TypeError, ValueError):
            pass

    products = Product.objects.select_related("category").filter(pk__in=ids).in_bulk()
    lines = []
    errors = []
    subtotal = Decimal("0")

    for item in cart:
        try:
            pid = int(item.get("product_id"))
            qty = Decimal(str(item.get("quantity", "0")))
        except (TypeError, ValueError, InvalidOperation):
            errors.append("Cart contains an invalid item.")
            continue

        sale_unit = item.get("sale_unit", "stock")
        product = products.get(pid)

        if product is None:
            errors.append("A product in the cart no longer exists.")
            continue

        if not product.is_active:
            errors.append(f"{product.name} is inactive.")
            continue

        if qty <= 0:
            continue

        available = product.current_stock or Decimal("0")

        if sale_unit == "purchase":
            wholesale = product.wholesale_price or Decimal("0")
            if wholesale <= 0:
                errors.append(f"{product.name} has no wholesale price set.")
                continue

            conversion = product.units_per_purchase_unit or Decimal("1")
            if conversion <= 0:
                errors.append(f"{product.name} has an invalid purchase conversion factor.")
                continue

            unit_price = wholesale
            stock_qty = (qty * conversion).quantize(THREE)
            display_unit = product.purchase_unit
        else:
            retail = product.unit_price or Decimal("0")
            if retail <= 0:
                errors.append(f"{product.name} has no retail price set.")
                continue

            unit_price = retail
            conversion = Decimal("1")
            stock_qty = qty.quantize(THREE)
            display_unit = product.stock_unit

        line_total = (qty * unit_price).quantize(TWO)

        if available < stock_qty:
            errors.append(
                f"Insufficient stock for {product.name}: available "
                f"{available.quantize(THREE)} {product.stock_unit}, needed "
                f"{stock_qty.quantize(THREE)} {product.stock_unit}."
            )

        average_cost = product.average_cost or Decimal("0")
        cost_basis = average_cost if product.cost_known and average_cost > 0 else Decimal("0")
        cost_total = (cost_basis * stock_qty).quantize(TWO) if cost_basis > 0 else Decimal("0")
        gross_profit = (line_total - cost_total).quantize(TWO) if cost_basis > 0 else Decimal("0")

        lines.append({
            "product": product,
            "quantity": qty,
            "sale_unit": sale_unit,
            "display_unit": display_unit,
            "unit_price": unit_price,
            "line_total": line_total,
            "stock_qty": stock_qty,
            "conversion": conversion,
            "cost_basis": cost_basis,
            "cost_total": cost_total,
            "gross_profit": gross_profit,
            "available": available,
        })

        subtotal += line_total

    subtotal = subtotal.quantize(TWO)
    totals = {
        "subtotal": subtotal,
        "discount_total": Decimal("0.00"),
        "grand_total": subtotal,
    }
    return lines, errors, totals


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return default


@pos_access_required
def pos_interface(request):
    q = request.GET.get("q", "").strip()
    results, fuzzy = _search_products(q)
    cart = _cart(request)
    lines, errors, totals = _build_lines(cart)

    return render(request, "pos/pos_interface.html", {
        "q": q,
        "results": results,
        "fuzzy": fuzzy,
        "cart_lines": lines,
        "cart_errors": errors,
        "totals": totals,
        "cart_count": len(lines),
    })


@require_POST
@pos_access_required
def add_to_cart(request):
    product_id = request.POST.get("product_id")
    quantity = _dec(request.POST.get("quantity", "1"))
    sale_unit = request.POST.get("sale_unit", "stock")

    if sale_unit not in ("stock", "purchase"):
        sale_unit = "stock"

    try:
        product = Product.objects.get(pk=product_id, is_active=True)
    except (Product.DoesNotExist, ValueError):
        messages.error(request, "Product not found.")
        return redirect("pos_interface")

    if quantity <= 0:
        messages.error(request, "Quantity must be greater than zero.")
        return redirect("pos_interface")

    if sale_unit == "stock" and (product.unit_price or Decimal("0")) <= 0:
        messages.error(request, f"{product.name} has no retail price set.")
        return redirect("pos_interface")

    if sale_unit == "purchase" and (product.wholesale_price or Decimal("0")) <= 0:
        messages.error(request, f"{product.name} has no wholesale price set.")
        return redirect("pos_interface")

    cart = _cart(request)
    idx = _find_cart_index(cart, product.pk, sale_unit)

    if idx >= 0:
        current = _dec(cart[idx].get("quantity", "0"))
        cart[idx]["quantity"] = str((current + quantity).quantize(THREE))
    else:
        cart.append({
            "product_id": product.pk,
            "sale_unit": sale_unit,
            "quantity": str(quantity.quantize(THREE)),
        })

    _save_cart(request, cart)
    messages.success(request, f"Added {product.name} to cart.")
    return redirect("pos_interface")


@require_POST
@pos_access_required
def update_cart(request):
    product_id = request.POST.get("product_id")
    sale_unit = request.POST.get("sale_unit", "stock")
    quantity = _dec(request.POST.get("quantity", "0"))

    cart = _cart(request)
    idx = _find_cart_index(cart, product_id, sale_unit)

    if idx < 0:
        messages.error(request, "Item not found in cart.")
        return redirect("pos_interface")

    if quantity <= 0:
        cart.pop(idx)
        messages.success(request, "Item removed.")
    else:
        cart[idx]["quantity"] = str(quantity.quantize(THREE))
        messages.success(request, "Cart updated.")

    _save_cart(request, cart)
    return redirect("pos_interface")


@require_POST
@pos_access_required
def remove_cart(request):
    product_id = request.POST.get("product_id")
    sale_unit = request.POST.get("sale_unit", "stock")

    cart = _cart(request)
    idx = _find_cart_index(cart, product_id, sale_unit)

    if idx >= 0:
        cart.pop(idx)
        _save_cart(request, cart)
        messages.success(request, "Item removed.")
    else:
        messages.error(request, "Item not found in cart.")

    return redirect("pos_interface")


@require_POST
@pos_access_required
def clear_cart(request):
    _clear_cart(request)
    messages.success(request, "Cart cleared.")
    return redirect("pos_interface")


@pos_access_required
def checkout(request):
    cart = _cart(request)
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("pos_interface")

    lines, errors, totals = _build_lines(cart)
    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect("pos_interface")

    key = uuid.uuid4().hex
    request.session[CHECKOUT_KEY_SESSION] = key

    return render(request, "pos/checkout.html", {
        "lines": lines,
        "totals": totals,
        "idempotency_key": key,
        "payment_methods": PosReceipt.PAYMENT_METHOD_CHOICES,
    })


@require_POST
@pos_access_required
def complete_sale(request):
    key = (request.POST.get("idempotency_key") or "").strip()
    if not key:
        messages.error(request, "Missing checkout token. Please try again.")
        return redirect("pos_checkout")

    existing = PosReceipt.objects.filter(idempotency_key=key).first()
    if existing:
        _clear_cart(request)
        return redirect("pos_receipt_detail", receipt_pk=existing.pk)

    cart = _cart(request)
    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("pos_interface")

    lines, errors, totals = _build_lines(cart)
    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect("pos_checkout")

    payment_method = request.POST.get("payment_method", "CASH")
    if payment_method not in dict(PosReceipt.PAYMENT_METHOD_CHOICES):
        messages.error(request, "Invalid payment method.")
        return redirect("pos_checkout")

    tendered = _dec(request.POST.get("amount_tendered", "0"))
    grand_total = totals["grand_total"]

    if tendered < grand_total:
        messages.error(request, "Amount tendered is less than the total sale.")
        return redirect("pos_checkout")

    change_due = (tendered - grand_total).quantize(TWO)
    reference = "POS-" + uuid.uuid4().hex[:10].upper()

    try:
        with transaction.atomic():
            receipt = PosReceipt.objects.create(
                reference=reference,
                staff_user=request.user,
                staff_username=request.user.username,
                business_date=business_today(),
                subtotal=totals["subtotal"],
                discount_total=totals["discount_total"],
                grand_total=grand_total,
                amount_tendered=tendered.quantize(TWO),
                change_due=change_due,
                payment_method=payment_method,
                status="COMPLETED",
                idempotency_key=key,
            )

            for line in lines:
                product = Product.objects.select_for_update().get(pk=line["product"].pk)

                if not product.is_active:
                    raise ValidationError(f"{product.name} is inactive.")

                stock_qty = line["stock_qty"]
                if (product.current_stock or Decimal("0")) < stock_qty:
                    raise ValidationError(
                        f"Insufficient stock for {product.name}. "
                        f"Available {product.current_stock} {product.stock_unit}."
                    )

                product.current_stock = (product.current_stock or Decimal("0")) - stock_qty
                product.save(update_fields=["current_stock"])

                StockMovement.objects.create(
                    product=product,
                    movement_type="OUT",
                    quantity=stock_qty.quantize(THREE),
                    reason="POS sale",
                    reference=reference,
                    performed_by=request.user,
                )

                average_cost = product.average_cost or Decimal("0")
                cost_basis = average_cost if product.cost_known and average_cost > 0 else Decimal("0")
                cost_total = (cost_basis * stock_qty).quantize(TWO) if cost_basis > 0 else Decimal("0")
                gross_profit = (line["line_total"] - cost_total).quantize(TWO) if cost_basis > 0 else Decimal("0")

                PosReceiptItem.objects.create(
                    receipt=receipt,
                    product=product,
                    product_name=product.name,
                    sku=product.sku,
                    stock_unit=product.stock_unit,
                    sale_unit=line["sale_unit"],
                    quantity=line["quantity"].quantize(THREE),
                    unit_price=line["unit_price"].quantize(TWO),
                    line_total=line["line_total"].quantize(TWO),
                    conversion_factor=line["conversion"].quantize(THREE),
                    stock_quantity_deducted=stock_qty.quantize(THREE),
                    cost_basis_per_unit=cost_basis.quantize(Decimal("0.0001")),
                    cost_basis_total=cost_total,
                    gross_profit=gross_profit,
                    cost_is_known=cost_basis > 0,
                )

        _clear_cart(request)
        messages.success(request, f"Sale completed: {reference}")
        return redirect("pos_receipt_detail", receipt_pk=receipt.pk)

    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("pos_checkout")
    except IntegrityError:
        existing = PosReceipt.objects.filter(idempotency_key=key).first()
        if existing:
            _clear_cart(request)
            return redirect("pos_receipt_detail", receipt_pk=existing.pk)
        messages.error(request, "Could not complete sale. Please try again.")
        return redirect("pos_checkout")


@pos_access_required
def receipt_detail(request, receipt_pk):
    receipt = get_object_or_404(PosReceipt.objects.prefetch_related("items__product"), pk=receipt_pk)

    if not (request.user.is_staff or request.user.is_superuser or receipt.staff_user_id == request.user.pk):
        messages.error(request, "You cannot view this receipt.")
        return redirect("pos_interface")

    return render(request, "pos/receipt_detail.html", {"receipt": receipt})


@pos_access_required
def my_transactions(request):
    receipts = PosReceipt.objects.filter(staff_user=request.user).prefetch_related("items").order_by("-created_at")
    return render(request, "pos/my_transactions.html", {"receipts": receipts})


@pos_access_required
def daily_sales(request):
    date = business_today()
    
    # 1. Find IDs of receipts already in active (non-rejected) submissions
    submitted_ids = DailySalesSubmission.objects.filter(
        staff_user=request.user, business_date=date
    ).exclude(status="REJECTED").values_list('receipts__id', flat=True)
    
    # 2. Get only the pending (unsubmitted) receipts
    pending_receipts = PosReceipt.objects.filter(
        staff_user=request.user, business_date=date, status="COMPLETED"
    ).exclude(id__in=submitted_ids)
    
    # 3. Summarize the pending receipts for the top cards
    pending_summary = summarize_receipts(pending_receipts)
    
    # 4. Get all submissions for today for the history table
    submissions = DailySalesSubmission.objects.filter(
        staff_user=request.user, business_date=date
    ).order_by('-submitted_at')

    return render(request, "pos/daily_sales.html", {
        "date": date,
        "pending_summary": pending_summary,
        "submissions": submissions,
    })


@require_POST
@pos_access_required
def submit_daily_sales(request):
    submission = submit_daily_sales_service(request.user)
    if submission:
        messages.success(request, f"Successfully submitted {submission.transaction_count} new sales! (Ref: {submission.reference})")
    else:
        messages.info(request, "No new sales to submit. Make a sale first, then come back to submit it!")
    return redirect("pos_daily_sales")

@management_required
def manager_daily_sales(request):
    today = business_today()
    date_str = request.GET.get("date")
    if date_str:
        date = _parse_date(date_str, today)
    else:
        latest_submission = DailySalesSubmission.objects.order_by("-business_date").first()
        date = latest_submission.business_date if latest_submission else today
    status = request.GET.get("status", "")

    submissions = (
        DailySalesSubmission.objects
        .select_related("staff_user")
        .filter(business_date=date)
        .order_by("-created_at")
    )

    if status in dict(DailySalesSubmission.STATUS_CHOICES):
        submissions = submissions.filter(status=status)

    combined = compute_date_summary(date)

    pending_count = DailySalesSubmission.objects.filter(status__in=["SUBMITTED", "UNDER_REVIEW"]).count()

    accepted_count = DailySalesSubmission.objects.filter(
        business_date=date,
        status="ACCEPTED",
    ).count()

    rejected_count = DailySalesSubmission.objects.filter(
        business_date=date,
        status="REJECTED",
    ).count()

    return render(request, "pos/manager_daily_sales.html", {
        "date": date,
        "today": today,
        "status": status,
        "status_choices": DailySalesSubmission.STATUS_CHOICES,
        "submissions": submissions,
        "combined": combined,
        "pending_count": pending_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
    })


@management_required
def manager_daily_sales_detail(request, submission_id):
    submission = get_object_or_404(
        DailySalesSubmission.objects.select_related("staff_user").prefetch_related("events__user"),
        pk=submission_id,
    )

    receipts = submission.receipts.filter(status="COMPLETED").prefetch_related("items__product")
    summary = summarize_receipts(receipts)

    return render(request, "pos/manager_daily_sales_detail.html", {
        "submission": submission,
        "receipts": receipts,
        "summary": summary,
        "events": submission.events.all(),
    })


@require_POST
@management_required
def manager_daily_sales_accept(request, submission_id):
    submission = get_object_or_404(DailySalesSubmission, pk=submission_id)

    try:
        accept_submission(submission, request.user)
        messages.success(request, f"Submission {submission.reference} accepted.")
    except ValidationError as exc:
        messages.error(request, str(exc))

    return redirect("manager_daily_sales_detail", submission_id=submission.pk)


@require_POST
@management_required
def manager_daily_sales_reject(request, submission_id):
    submission = get_object_or_404(DailySalesSubmission, pk=submission_id)
    reason = request.POST.get("reason", "").strip()

    try:
        reject_submission(submission, request.user, reason)
        messages.success(request, f"Submission {submission.reference} rejected.")
    except ValidationError as exc:
        messages.error(request, str(exc))

    return redirect("manager_daily_sales_detail", submission_id=submission.pk)
