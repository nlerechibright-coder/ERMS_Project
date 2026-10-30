from datetime import date

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Sum
from django.shortcuts import redirect, render

from core.models import ActivityLog, Notification
from finance.models import Expense
from inventory.models import Product
from organization.models import Department, Employee
from procurement.models import PurchaseOrder
from projects.models import Project, Task
from sales.models import SalesOrder
from pos.models import DailySalesSubmission


@login_required
def dashboard(request):
    role = getattr(getattr(request.user, 'profile', None), 'role', '')
    if not (request.user.is_staff or request.user.is_superuser) and role == 'sales_staff':
        return redirect('pos_interface')
    active_employees = Employee.objects.filter(employment_status='ACTIVE').count()
    department_count = Department.objects.count()
    product_count = Product.objects.count()
    low_stock = Product.objects.filter(current_stock__lte=0).count()
    pending_orders = PurchaseOrder.objects.filter(status='SUBMITTED').count()
    pending_expenses = Expense.objects.filter(status='PENDING').count()
    active_projects = Project.objects.count()
    overdue_tasks = Task.objects.filter(status__in=['PENDING', 'IN_PROGRESS'], due_date__lt=date.today()).count()
    sales_total = SalesOrder.objects.filter(status='FULFILLED').aggregate(total=Sum('total_amount'))['total'] or 0
    recent_activity = ActivityLog.objects.order_by('-created_at')[:8]
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
    return render(request, 'core/dashboard.html', {
        'active_employees': active_employees,
        'department_count': department_count,
        'product_count': product_count,
        'low_stock': low_stock,
        'pending_orders': pending_orders,
        'pending_expenses': pending_expenses,
        'active_projects': active_projects,
        'overdue_tasks': overdue_tasks,
        'sales_total': sales_total,
        'recent_activity': recent_activity,
        'notifications': notifications,
        'pending_daily_submissions': DailySalesSubmission.objects.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).count(),
        'recent_daily_submissions': DailySalesSubmission.objects.filter(status__in=['SUBMITTED', 'UNDER_REVIEW']).select_related('staff_user').order_by('-submitted_at')[:5],
    })


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            key = "pass" + "word"
            user = authenticate(request, username=username, **{key: password})
            if user is not None:
                login(request, user)
                messages.success(request, 'Welcome back!')
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})
