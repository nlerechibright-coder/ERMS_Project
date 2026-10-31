from decimal import Decimal

from django.contrib import messages
from core.decorators import management_required
from django.db import transaction
from django.shortcuts import redirect, render

from inventory.models import Product, StockMovement
from .models import Customer, SalesOrder, SalesOrderLineItem


@management_required
def customer_list(request):
    if request.method == "POST":
        from sales.models import Customer
        name = request.POST.get('name', '').strip()
        if name:
            Customer.objects.create(name=name, company=request.POST.get('company', ''), email=request.POST.get('email', ''), phone=request.POST.get('phone', ''), address=request.POST.get('address', ''))
            messages.success(request, f'Customer {name} added.')
        return redirect('customer_list')
    customers = Customer.objects.order_by('name')
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can manage customers.')
            return redirect('customer_list')
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Customer name is required.')
            return redirect('customer_list')
        customer = Customer.objects.create(
            name=name,
            email=request.POST.get('email', '').strip(),
            phone=request.POST.get('phone', '').strip(),
            company=request.POST.get('company', '').strip(),
        )
        messages.success(request, f'Customer {customer.name} created.')
        return redirect('customer_list')
    return render(request, 'sales/customer_list.html', {'customers': customers})


@management_required
def customer_edit(request, customer_id):
    customer = Customer.objects.get(pk=customer_id)
    if request.method == 'POST':
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(request, 'Only managers can edit customers.')
            return redirect('customer_list')
        customer.name = request.POST.get('name', customer.name).strip()
        customer.email = request.POST.get('email', '').strip()
        customer.phone = request.POST.get('phone', '').strip()
        customer.company = request.POST.get('company', '').strip()
        customer.is_active = request.POST.get('is_active') == 'on'
        customer.save()
        messages.success(request, 'Customer updated.')
        return redirect('customer_list')
    return render(request, 'sales/customer_form.html', {'customer': customer})


@management_required
def sales_order_list(request):
    orders = SalesOrder.objects.select_related('customer').order_by('-order_date', '-id')
    return render(request, 'sales/sales_order_list.html', {'orders': orders})


@management_required
def sales_order_create(request):
    if request.method == 'POST':
        customer_id = request.POST.get('customer')
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            messages.error(request, 'Customer is required.')
            return redirect('sales_order_list')
        order_number = request.POST.get('order_number', '').strip() or f'SO-{customer.id}-{SalesOrder.objects.count() + 1}'
        order = SalesOrder.objects.create(customer=customer, order_number=order_number, status='DRAFT', created_by=request.user, notes=request.POST.get('notes', ''))
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        for idx, product_value in enumerate(product_ids):
            if not product_value:
                continue
            product = Product.objects.filter(pk=product_value).first()
            if not product:
                continue
            quantity = int(quantities[idx] or 0)
            unit_price = Decimal(prices[idx] or '0')
            if quantity > 0:
                SalesOrderLineItem.objects.create(sales_order=order, product=product, quantity=quantity, unit_price=unit_price)
        order.recalculate_total()
        messages.success(request, 'Sales order created.')
        return redirect('sales_order_list')
    return render(request, 'sales/sales_order_form.html', {'customers': Customer.objects.filter(is_active=True), 'products': Product.objects.filter(is_active=True)})


@management_required
def sales_order_edit(request, order_id):
    order = SalesOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        order.notes = request.POST.get('notes', '')
        order.save(update_fields=['notes'])
        order.line_items.all().delete()
        product_ids = request.POST.getlist('product')
        quantities = request.POST.getlist('quantity')
        prices = request.POST.getlist('unit_price')
        for idx, product_value in enumerate(product_ids):
            if not product_value:
                continue
            product = Product.objects.filter(pk=product_value).first()
            if not product:
                continue
            quantity = int(quantities[idx] or 0)
            unit_price = Decimal(prices[idx] or '0')
            if quantity > 0:
                SalesOrderLineItem.objects.create(sales_order=order, product=product, quantity=quantity, unit_price=unit_price)
        order.recalculate_total()
        messages.success(request, 'Sales order updated.')
        return redirect('sales_order_list')
    return render(request, 'sales/sales_order_form.html', {'order': order, 'customers': Customer.objects.filter(is_active=True), 'products': Product.objects.filter(is_active=True)})


@management_required
def sales_order_confirm(request, order_id):
    order = SalesOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if order.status == 'FULFILLED':
            messages.error(request, 'This order is already fulfilled.')
            return redirect('sales_order_list')
        order.status = 'CONFIRMED'
        order.confirmed_by = request.user
        order.save(update_fields=['status', 'confirmed_by'])
        messages.success(request, 'Sales order confirmed.')
    return redirect('sales_order_list')


@management_required
def sales_order_fulfill(request, order_id):
    order = SalesOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if order.status == 'FULFILLED':
            messages.error(request, 'This order cannot be fulfilled twice.')
            return redirect('sales_order_list')
        if order.status != 'CONFIRMED':
            messages.error(request, 'Only confirmed orders can be fulfilled.')
            return redirect('sales_order_list')
        with transaction.atomic():
            for line in order.line_items.all():
                if line.product.current_stock < line.quantity:
                    raise ValueError(f'Not enough stock for {line.product.name}.')
                line.product.current_stock -= line.quantity
                line.product.save(update_fields=['current_stock'])
                StockMovement.objects.create(
                    product=line.product,
                    movement_type='OUT',
                    quantity=line.quantity,
                    reason='Sales fulfillment',
                    reference=order.order_number,
                    performed_by=request.user,
                )
            order.status = 'FULFILLED'
            order.save(update_fields=['status'])
        messages.success(request, 'Sales order fulfilled and stock deducted.')
    return redirect('sales_order_list')


@management_required
def sales_order_cancel(request, order_id):
    order = SalesOrder.objects.get(pk=order_id)
    if request.method == 'POST':
        if order.status == 'FULFILLED':
            messages.error(request, 'A fulfilled order cannot be cancelled.')
            return redirect('sales_order_list')
        order.status = 'CANCELLED'
        order.save(update_fields=['status'])
        messages.success(request, 'Sales order cancelled.')
    return redirect('sales_order_list')
