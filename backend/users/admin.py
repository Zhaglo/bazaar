from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
    ("Role", {"fields": ("role",)}),
    )
    list_display = ('username', 'role', 'display_name', 'phone', 'email', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser')
