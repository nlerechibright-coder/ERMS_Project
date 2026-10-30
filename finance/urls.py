from django.urls import path

from . import views

urlpatterns = [
    path('', views.expense_list, name='expense_list'),
    path('categories/', views.expense_category_list, name='expense_category_list'),
    path('<int:expense_id>/approve/', views.expense_approve, name='expense_approve'),
    path('<int:expense_id>/reject/', views.expense_reject, name='expense_reject'),
    path('<int:expense_id>/pay/', views.payment_entry_create, name='payment_entry_create'),
]
