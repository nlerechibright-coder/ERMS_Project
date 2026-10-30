from django.urls import path

from . import views

urlpatterns = [
    path("", views.pos_interface, name="pos_interface"),
    path("add/", views.add_to_cart, name="pos_add_to_cart"),
    path("update/", views.update_cart, name="pos_update_cart"),
    path("remove/", views.remove_cart, name="pos_remove_cart"),
    path("clear/", views.clear_cart, name="pos_clear_cart"),
    path("checkout/", views.checkout, name="pos_checkout"),
    path("complete/", views.complete_sale, name="pos_complete_sale"),
    path("receipt/<int:receipt_pk>/", views.receipt_detail, name="pos_receipt_detail"),
    path("transactions/", views.my_transactions, name="pos_my_transactions"),

    path("daily-sales/", views.daily_sales, name="pos_daily_sales"),
    path("daily-sales/submit/", views.submit_daily_sales, name="pos_daily_sales_submit"),

    path("manager/daily-sales/", views.manager_daily_sales, name="manager_daily_sales"),
    path("manager/daily-sales/<int:submission_id>/", views.manager_daily_sales_detail, name="manager_daily_sales_detail"),
    path("manager/daily-sales/<int:submission_id>/accept/", views.manager_daily_sales_accept, name="manager_daily_sales_accept"),
    path("manager/daily-sales/<int:submission_id>/reject/", views.manager_daily_sales_reject, name="manager_daily_sales_reject"),
]
