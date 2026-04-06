from django.conf import settings
from django.db import models
from shops.models import Shop, CatalogItem

class Order(models.Model):
    """
    Модель заказа клиента.

    Представляет собой заказ, сделанный клиентом в определённом магазине.
    Содержит информацию о клиенте, магазине, статусе заказа, общей стоимости,
    адресе доставки и времени создания.

    Attributes:
        client (ForeignKey): Ссылка на пользователя-клиента (AUTH_USER_MODEL).
        shop (ForeignKey): Ссылка на магазин (модель Shop).
        status (CharField): Текущий статус заказа (NEW, ASSEMBLING, READY, ON_DELIVERY, DELIVERED, CANCELLED).
        created_at (DateTimeField): Дата и время создания заказа (автоматически).
        total_price (DecimalField): Общая стоимость заказа (сумма позиций).
        delivery_address (CharField): Адрес доставки (улица, дом, квартира и т.д.).
    """

    class Status(models.TextChoices):
        """Допустимые статусы заказа."""
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
        """
        Возвращает строковое представление заказа.

        Returns:
            str: Строка вида 'Order #<id> (<status>)'.
        """
        return f"Order #{self.id} ({self.status})"


class OrderItem(models.Model):
    """
    Позиция заказа (строка заказа).

    Соответствует одному товару (CatalogItem) в составе конкретного заказа.
    Хранит количество единиц товара и цену на момент заказа (для защиты от изменений цены в каталоге).

    Attributes:
        order (ForeignKey): Заказ, к которому относится позиция.
        catalog_item (ForeignKey): Товар из каталога магазина.
        quantity (PositiveIntegerField): Количество единиц товара.
        price_at_moment (DecimalField): Цена товара на момент оформления заказа.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    catalog_item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price_at_moment = models.DecimalField(max_digits=8, decimal_places=2)

    def __str__(self):
        """
        Возвращает строковое представление позиции заказа.

        Returns:
            str: Строка вида '<название товара> x <количество>'.
        """
        return f'{self.catalog_item.name} x {self.quantity}'

    def get_total(self):
        """
        Вычисляет общую стоимость данной позиции заказа.

        Returns:
            Decimal: Стоимость = price_at_moment * quantity.
        """
        return self.price_at_moment * self.quantity
