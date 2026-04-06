from django.conf import settings
from django.db import models

class Shop(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shops',
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CatalogSection(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="catalog_sections",
    )
    name = models.CharField("Название раздела", max_length=255)
    ordering = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self):
        return f"{self.shop.name}: {self.name}"


class CatalogItem(models.Model):
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='catalog_items',
    )
    section = models.ForeignKey(
        CatalogSection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='items',
        verbose_name='Раздел каталога',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} ({self.shop.name})'


class ShopApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "На рассмотрении"
        APPROVED = "APPROVED", "Одобрена"
        REJECTED = "REJECTED", "Отклонена"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shop_applications",
        verbose_name="Пользователь",
    )

    shop_name = models.CharField("Название магазина", max_length=255)
    address = models.CharField("Адрес", max_length=255)
    description = models.TextField("Описание магазина", blank=True)

    contact_name = models.CharField("Контактное лицо", max_length=255)
    contact_phone = models.CharField("Телефон", max_length=50)
    comment = models.TextField("Комментарий", blank=True)

    status = models.CharField(
        "Статус заявки",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField("Создана", auto_now_add=True)
    processed_at = models.DateTimeField("Обработана", null=True, blank=True)

    def __str__(self):
        return f"Заявка магазина #{self.id} ({self.shop_name})"
