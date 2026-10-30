from django.urls import path

from . import views

urlpatterns = [
    path('categories/', views.product_category_list, name='product_category_list'),
    path('', views.product_list, name='product_list'),
    path('new/', views.product_list, name='product_create'),
    path('<int:product_id>/edit/', views.product_edit, name='product_edit'),
    path('<int:product_id>/deactivate/', views.product_deactivate, name='product_deactivate'),
    path('movements/', views.stock_movement_list, name='stock_movement_list'),
    path('movements/new/', views.stock_movement_create, name='stock_movement_create'),
    path('receipts/', views.stock_receipt_list, name='stock_receipt_list'),
    path('receipts/new/', views.stock_receipt_create, name='stock_receipt_create'),
    path('receipts/<int:receipt_id>/confirm/', views.stock_receipt_confirm, name='stock_receipt_confirm'),
    path('summary/', views.stock_summary, name='stock_summary'),
]
