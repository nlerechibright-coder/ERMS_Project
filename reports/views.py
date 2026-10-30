import csv

from django.contrib import messages
from core.decorators import management_required
from django.db import models
from django.http import HttpResponse
from django.shortcuts import render

from finance.models import Expense
from inventory.models import Product, StockMovement
from organization.models import Employee
from procurement.models import GoodsReceipt, PurchaseOrder
from projects.models import Project, Task
from sales.models import SalesOrder


@management_required
def report_dashboard(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You do not have access to the reports dashboard.')
        return render(request, 'reports/report_dashboard.html', {'title': 'Reports', 'restricted': True})

    data = {
        'employees': Employee.objects.filter(is_active=True).count(),
        'products': Product.objects.filter(is_active=True).count(),
        'low_stock': Product.objects.filter(is_active=True, current_stock__lte=models.F('reorder_level')).count(),
        'purchase_orders': PurchaseOrder.objects.count(),
        'sales_orders': SalesOrder.objects.count(),
        'expenses': Expense.objects.filter(status='APPROVED').count(),
        'projects': Project.objects.count(),
        'open_tasks': Task.objects.filter(status__in=['PENDING', 'IN_PROGRESS']).count(),
    }
    return render(request, 'reports/report_dashboard.html', {'title': 'Reports', **data})


@management_required
def export_csv(request, report_type):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You do not have access to CSV exports.')
        return render(request, 'reports/report_dashboard.html', {'title': 'Reports', 'restricted': True})

    model_map = {
        'employees': Employee.objects.filter(is_active=True),
        'stock-movements': StockMovement.objects.select_related('product', 'performed_by'),
        'purchase-orders': PurchaseOrder.objects.select_related('supplier'),
        'sales-orders': SalesOrder.objects.select_related('customer'),
        'expenses': Expense.objects.select_related('category', 'submitted_by'),
        'projects': Project.objects.select_related('manager'),
        'tasks': Task.objects.select_related('project', 'assigned_to'),
    }

    queryset = model_map.get(report_type)
    if queryset is None:
        return render(request, 'reports/report_dashboard.html', {'title': 'Reports', 'restricted': False})

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    safe_name = report_type.replace('-', '_')
    response['Content-Disposition'] = f'attachment; filename="{safe_name}.csv"; filename*=UTF-8\'\'{safe_name}.csv'
    writer = csv.writer(response)
    if report_type == 'employees':
        writer.writerow(['id', 'first_name', 'last_name', 'email', 'department', 'position', 'status'])
        for item in queryset:
            writer.writerow([item.id, item.first_name, item.last_name, item.email, item.department.name if item.department else '', item.position, item.employment_status])
    elif report_type == 'stock-movements':
        writer.writerow(['id', 'product', 'type', 'quantity', 'reason', 'reference', 'performed_by', 'created_at'])
        for item in queryset:
            writer.writerow([item.id, item.product.name, item.movement_type, item.quantity, item.reason, item.reference, item.performed_by.username if item.performed_by else '', item.created_at.isoformat()])
    elif report_type == 'purchase-orders':
        writer.writerow(['id', 'order_number', 'supplier', 'status', 'total_amount', 'order_date'])
        for item in queryset:
            writer.writerow([item.id, item.order_number, item.supplier.name, item.status, item.total_amount, item.order_date.isoformat()])
    elif report_type == 'sales-orders':
        writer.writerow(['id', 'order_number', 'customer', 'status', 'total_amount', 'order_date'])
        for item in queryset:
            writer.writerow([item.id, item.order_number, item.customer.name, item.status, item.total_amount, item.order_date.isoformat()])
    elif report_type == 'expenses':
        writer.writerow(['id', 'title', 'category', 'amount', 'status', 'expense_date'])
        for item in queryset:
            writer.writerow([item.id, item.title, item.category.name if item.category else '', item.amount, item.status, item.expense_date.isoformat()])
    elif report_type == 'projects':
        writer.writerow(['id', 'name', 'status', 'priority', 'budget', 'progress'])
        for item in queryset:
            writer.writerow([item.id, item.name, item.status, item.priority, item.budget, item.progress])
    elif report_type == 'tasks':
        writer.writerow(['id', 'title', 'project', 'status', 'priority', 'due_date', 'assigned_to'])
        for item in queryset:
            writer.writerow([item.id, item.title, item.project.name, item.status, item.priority, item.due_date.isoformat() if item.due_date else '', item.assigned_to.username if item.assigned_to else ''])
    return response
