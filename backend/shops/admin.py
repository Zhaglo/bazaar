from django.contrib import admin
from .models import Shop, CatalogItem, CatalogSection, ShopApplication

class CatalogItemInline(admin.TabularInline):
    model = CatalogItem
    extra = 0


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'address')
    search_fields = ('name', 'address')


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'price', 'is_available')
    list_filter = ('shop', 'is_available')
    search_fields = ('name',)


@admin.register(ShopApplication)
class ShopApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "shop_name", "contact_name", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("shop_name", "contact_name", "contact_phone", "comment")
    readonly_fields = ("created_at", "processed_at")


@admin.register(CatalogSection)
class CatalogSectionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "shop", "ordering")
    list_filter = ("shop",)
    search_fields = ("name", "shop__name")
    inlines = [CatalogItemInline]
