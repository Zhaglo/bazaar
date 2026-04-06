from django.conf import settings
from django.db import models
from orders.models import Order

class CourierProfile(models.Model):
    """
    Профиль курьера, привязанный к пользователю.

    Хранит информацию о типе транспорта курьера и его активности.
    Связан с моделью пользователя (AUTH_USER_MODEL) отношением один-к-одному.

    Attributes:
        user (OneToOneField): Ссылка на объект пользователя (владельца профиля).
        vehicle_type (CharField): Тип транспорта (пешком, велосипед, авто).
        is_active (BooleanField): Статус активности курьера (может ли принимать заказы).
    """

    class VehicleTypes(models.TextChoices):
        """Допустимые типы транспортных средств курьера."""
        FOOT = 'FOOT', 'On foot'
        BIKE = 'BIKE', 'Bike'
        CAR = 'CAR', 'Car'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='courier_profile',
    )
    vehicle_type = models.CharField(
        max_length=10,
        choices=VehicleTypes.choices,
        default=VehicleTypes.FOOT,
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """Возвращает строковое представление профиля курьера в виде 'Courier {username}'."""
        return f'Courier {self.user.username}'


class DeliveryTask(models.Model):
    """
    Задание на доставку, связанное с одним заказом.

    Определяет, какой курьер доставляет заказ, статус выполнения,
    а также временные метки назначения и завершения.

    Attributes:
        order (OneToOneField): Заказ, к которому привязана доставка.
        courier (ForeignKey): Курьер, назначенный на доставку (может быть NULL).
        status (CharField): Текущий статус доставки (PENDING, ASSIGNED, IN_PROGRESS, DONE).
        assigned_at (DateTimeField): Время назначения курьера (если назначен).
        completed_at (DateTimeField): Время завершения доставки (если завершена).
    """

    class Status(models.TextChoices):
        """Статусы выполнения задания доставки."""
        PENDING = 'PENDING', 'Pending'
        ASSIGNED = 'ASSIGNED', 'Assigned'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        DONE = 'DONE', 'Done'

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='delivery_task',
    )
    courier = models.ForeignKey(
        CourierProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        """Возвращает строку вида 'Delivery for order #{id} (status)'."""
        return f'Delivery for order #{self.order.id} ({self.status})'


class CourierApplication(models.Model):
    """
    Заявка от пользователя (или гостя) на становление курьером.

    Хранит персональные данные, тип транспорта, комментарий,
    статус рассмотрения и временные метки.

    Attributes:
        user (ForeignKey): Пользователь, подавший заявку (может быть NULL для гостя).
        full_name (CharField): Полное имя заявителя.
        phone (CharField): Контактный телефон.
        vehicle_type (CharField): Тип транспорта (свободное текстовое поле).
        comment (TextField): Дополнительная информация от заявителя.
        status (CharField): Статус рассмотрения (PENDING, APPROVED, REJECTED).
        created_at (DateTimeField): Дата и время создания заявки.
        processed_at (DateTimeField): Дата и время обработки заявки (если обработана).
    """

    class Status(models.TextChoices):
        """Статус обработки заявки курьера."""
        PENDING = "PENDING", "На рассмотрении"
        APPROVED = "APPROVED", "Одобрена"
        REJECTED = "REJECTED", "Отклонена"

    # Пользователь, оставивший заявку (может быть null, если заявка от гостя)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courier_applications",
    )

    full_name = models.CharField("ФИО", max_length=255)
    phone = models.CharField("Телефон", max_length=50)
    vehicle_type = models.CharField(
        "Тип транспорта",
        max_length=50,
        blank=True,
        help_text="Например: пешком, велосипед, авто",
    )
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
        """Возвращает строку вида 'Заявка курьера #{id} (ФИО)'."""
        return f"Заявка курьера #{self.id} ({self.full_name})"
