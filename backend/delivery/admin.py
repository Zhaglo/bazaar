from django.contrib import admin
from .models import CourierProfile, DeliveryTask, CourierApplication

@admin.register(DeliveryTask)
class DeliveryTaskAdmin(admin.ModelAdmin):
    list_display = ('order', 'courier', 'status', 'assigned_at', 'completed_at')
    list_filter = ('status',)


@admin.register(CourierProfile)
class CourierProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle_type', 'is_active')
    list_filter = ('vehicle_type', 'is_active')


@admin.register(CourierApplication)
class CourierApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "phone", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("full_name", "phone", "comment")
    readonly_fields = ("created_at", "processed_at")
