# payments/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('create/', views.create_payment, name='create_payment'),
    path('confirm/', views.confirm_payment, name='confirm_payment'),
    path('transactions/', views.get_transaction_history, name='transaction_history'),
    path('transactions/<uuid:transaction_id>/', views.get_transaction_detail, name='transaction_detail'),
    path('transactions/<uuid:transaction_id>/receipt/', views.download_receipt, name='download_receipt'),
    path('wallet/', views.get_wallet, name='get_wallet'),
    path('wallet/add-balance/', views.add_balance, name='add_balance'),
    path('webhook/', views.webhook_callback, name='webhook'),
    path('', views.home_page, name='home'),
    path('refund/cancel/', views.process_cancellation_refund, name='refund_cancel'),
    path('refund/status/<uuid:booking_id>/', views.get_refund_status, name='refund_status'),
    path('refund/rules/', views.get_refund_rules, name='refund_rules'),
]