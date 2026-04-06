from django.conf import settings
from django.db import models
from shops.models import Shop, CatalogItem

class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'NEW', 'New'
        COOKING = 'ASSEMBLING', 'Assembling'
        READY = 'READY', 'Ready'
        ON_DELIVERY = 'ON_DELIVERY', 'On delivery'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.NEW,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    delivery_address = models.CharField(max_length=255)

    def __str__(self):
        return f"Order #{self.id} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price_at_moment = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        return f'{self.catalog_item.name} x {self.quantity}'

    def get_total(self):
        return self.price_at_moment * self.quantity
