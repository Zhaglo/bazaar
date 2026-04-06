from django.conf import settings
from django.db import models

class Shop(models.Model):
    """
    Модель магазина (партнёра), зарегистрированного на платформе.

    Каждый магазин принадлежит одному пользователю-владельцу (роль SHOP).
    Содержит основную информацию: название, адрес, описание.

    Attributes:
        owner (ForeignKey): Владелец магазина (пользователь с ролью SHOP).
        name (CharField): Название магазина.
        address (CharField): Физический адрес магазина.
        description (TextField): Описание магазина (ассортимент, время работы и т.д.).
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shops',
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self):
        """Возвращает название магазина."""
        return self.name


class CatalogSection(models.Model):
    """
    Раздел каталога товаров внутри магазина.

    Позволяет группировать товары по категориям (например, «Овощи», «Молочные продукты»).
    Порядок отображения разделов задаётся полем ordering.

    Attributes:
        shop (ForeignKey): Магазин, которому принадлежит раздел.
        name (CharField): Название раздела.
        ordering (PositiveIntegerField): Порядок сортировки при отображении (по возрастанию).
    """

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
        """Возвращает строку вида 'Название_магазина: Название_раздела'."""
        return f"{self.shop.name}: {self.name}"


class CatalogItem(models.Model):
    """
    Товар в каталоге магазина.

    Принадлежит конкретному магазину и опционально – разделу каталога.
    Содержит цену, описание и флаг доступности.

    Attributes:
        shop (ForeignKey): Магазин, в котором продаётся товар.
        section (ForeignKey): Раздел каталога (может быть NULL, если раздел не указан).
        name (CharField): Название товара.
        description (TextField): Описание товара.
        price (DecimalField): Цена товара.
        is_available (BooleanField): Доступен ли товар для заказа (по умолчанию True).
    """

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
        """Возвращает строку вида 'Название товара (Название магазина)'."""
        return f'{self.name} ({self.shop.name})'


class ShopApplication(models.Model):
    """
    Заявка от пользователя на регистрацию нового магазина на платформе.

    Подаётся пользователем (авторизованным или гостем? здесь user может быть null).
    Содержит контактные данные и информацию о магазине.
    Администратор платформы обрабатывает заявку, меняя статус.

    Attributes:
        user (ForeignKey): Пользователь, подавший заявку (может быть NULL для гостя).
        shop_name (CharField): Желаемое название магазина.
        address (CharField): Адрес магазина.
        description (TextField): Описание магазина.
        contact_name (CharField): Контактное лицо (ФИО).
        contact_phone (CharField): Телефон для связи.
        comment (TextField): Дополнительная информация от заявителя.
        status (CharField): Статус рассмотрения (PENDING, APPROVED, REJECTED).
        created_at (DateTimeField): Дата и время создания заявки.
        processed_at (DateTimeField): Дата и время обработки заявки (если обработана).
    """

    class Status(models.TextChoices):
        """Статусы обработки заявки на регистрацию магазина."""
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
        """Возвращает строку вида 'Заявка магазина #<id> (Название магазина)'."""
        return f"Заявка магазина #{self.id} ({self.shop_name})"
