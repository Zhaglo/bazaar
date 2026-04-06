from django.conf import settings
from django.db import models
from orders.models import Order

class CourierProfile(models.Model):
    class VehicleTypes(models.TextChoices):
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
        return f'Courier {self.user.username}'


class DeliveryTask(models.Model):
    class Status(models.TextChoices):
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
        return f'Delivery for order #{self.order.id} ({self.status})'


class CourierApplication(models.Model):
    class Status(models.TextChoices):
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
        return f"Заявка курьера #{self.id} ({self.full_name})"
