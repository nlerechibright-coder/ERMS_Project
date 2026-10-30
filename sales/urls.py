from django.urls import path

from . import views

urlpatterns = [
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:customer_id>/edit/', views.customer_edit, name='customer_edit'),
    path('orders/', views.sales_order_list, name='sales_order_list'),
    path('orders/new/', views.sales_order_create, name='sales_order_create'),
    path('orders/<int:order_id>/edit/', views.sales_order_edit, name='sales_order_edit'),
    path('orders/<int:order_id>/confirm/', views.sales_order_confirm, name='sales_order_confirm'),
    path('orders/<int:order_id>/fulfill/', views.sales_order_fulfill, name='sales_order_fulfill'),
    path('orders/<int:order_id>/cancel/', views.sales_order_cancel, name='sales_order_cancel'),
]
