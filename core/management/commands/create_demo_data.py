from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from organization.models import Department, Employee
from inventory.models import ProductCategory, Product
from procurement.models import Supplier, PurchaseOrder
from sales.models import Customer, SalesOrder
from projects.models import Project, Task
from finance.models import ExpenseCategory, Expense

class Command(BaseCommand):
    help = 'Creates safe, realistic, idempotent sample data for testing and screenshots.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting sample data population...'))

        User = get_user_model()
        # Use harry123 if it exists, otherwise create a manager
        manager_user, _ = User.objects.get_or_create(
            username='harry123',
            defaults={'is_staff': True, 'is_superuser': False}
        )

        # 1. Organization
        dept, _ = Department.objects.get_or_create(name='Information Technology')
        
        emp1, _ = Employee.objects.get_or_create(
            first_name='John', last_name='Doe',
            defaults={'department': dept, 'employment_status': 'ACTIVE', 'position': 'Developer', 'email': 'john.doe@example.com'}
        )
        emp2, _ = Employee.objects.get_or_create(
            first_name='Jane', last_name='Smith',
            defaults={'department': dept, 'employment_status': 'ACTIVE', 'position': 'Manager', 'email': 'jane.smith@example.com'}
        )

        # 2. Inventory
        cat, _ = ProductCategory.objects.get_or_create(name='Electronics')
        
        prod1, _ = Product.objects.get_or_create(
            sku='LAP-001',
            defaults={'name': 'Business Laptop', 'category': cat, 'unit_price': 1200.00, 'current_stock': 5, 'reorder_level': 10, 'is_active': True}
        )
        prod2, _ = Product.objects.get_or_create(
            sku='MOU-001',
            defaults={'name': 'Wireless Mouse', 'category': cat, 'unit_price': 25.00, 'current_stock': 50, 'reorder_level': 10, 'is_active': True}
        )
        prod3, _ = Product.objects.get_or_create(
            sku='MON-001',
            defaults={'name': '27-inch Monitor', 'category': cat, 'unit_price': 300.00, 'current_stock': 15, 'reorder_level': 5, 'is_active': True}
        )

        # 3. Procurement
        supplier, _ = Supplier.objects.get_or_create(
            name='Tech Supplies Inc.',
            defaults={'contact_person': 'Sales Rep', 'email': 'sales@techsupplies.com', 'is_active': True}
        )
        po, _ = PurchaseOrder.objects.get_or_create(
            order_number='PO-2023-001',
            defaults={'supplier': supplier, 'status': 'SUBMITTED', 'submitted_by': manager_user}
        )

        # 4. Sales
        customer, _ = Customer.objects.get_or_create(
            name='Global Corp',
            defaults={'email': 'contact@globalcorp.com', 'is_active': True}
        )
        so, _ = SalesOrder.objects.get_or_create(
            order_number='SO-2023-001',
            defaults={'customer': customer, 'status': 'CONFIRMED', 'total_amount': 1200.00, 'created_by': manager_user}
        )

        # 5. Projects & Tasks
        proj, _ = Project.objects.get_or_create(
            name='Website Redesign',
            defaults={'status': 'IN_PROGRESS', 'priority': 'HIGH', 'budget': 5000.00, 'manager': manager_user}
        )
        task1, _ = Task.objects.get_or_create(
            project=proj, title='Finalize Mockups',
            defaults={'status': 'PENDING', 'priority': 'HIGH', 'assigned_to': manager_user}
        )
        task2, _ = Task.objects.get_or_create(
            project=proj, title='Setup CI/CD Pipeline',
            defaults={'status': 'COMPLETED', 'priority': 'MEDIUM', 'assigned_to': manager_user}
        )

        # 6. Finance
        exp_cat, _ = ExpenseCategory.objects.get_or_create(name='Software & Tools')
        exp1, _ = Expense.objects.get_or_create(
            title='GitHub Enterprise License',
            defaults={'category': exp_cat, 'amount': 299.99, 'status': 'PENDING', 'submitted_by': manager_user}
        )
        exp2, _ = Expense.objects.get_or_create(
            title='Cloud Hosting',
            defaults={'category': exp_cat, 'amount': 150.00, 'status': 'APPROVED', 'submitted_by': manager_user}
        )

        self.stdout.write(self.style.SUCCESS('Sample data population completed successfully!'))
        self.stdout.write(self.style.WARNING('Note: Sales Order SO-2023-001 is CONFIRMED. You can test the "Fulfill" workflow to see stock deduct.'))
