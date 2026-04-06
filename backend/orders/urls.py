from django.urls import path
from . import views

urlpatterns = [
    path('orders/', views.order_list_or_create, name='order_list_or_create'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/status/', views.order_change_status, name='order_change_status'),
]