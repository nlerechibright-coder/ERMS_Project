from django.urls import path

from . import views

urlpatterns = [
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/<int:supplier_id>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<int:supplier_id>/delete/', views.supplier_delete, name='supplier_delete'),
    path('purchase-orders/', views.purchase_order_list, name='purchase_order_list'),
    path('purchase-orders/new/', views.purchase_order_create, name='purchase_order_create'),
    path('purchase-orders/<int:order_id>/edit/', views.purchase_order_edit, name='purchase_order_edit'),
    path('purchase-orders/<int:order_id>/submit/', views.purchase_order_submit, name='purchase_order_submit'),
    path('purchase-orders/<int:order_id>/approve/', views.purchase_order_approve, name='purchase_order_approve'),
    path('purchase-orders/<int:order_id>/reject/', views.purchase_order_reject, name='purchase_order_reject'),
    path('purchase-orders/<int:order_id>/receive/', views.goods_receipt_create, name='goods_receipt_create'),
]
