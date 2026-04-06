from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Roles(models.TextChoices):
        CLIENT = "CLIENT", "client"
        RESTAURANT = "SHOP", "shop"
        COURIER = "COURIER", "courier"
        ADMIN = "ADMIN", "admin"

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.CLIENT,
    )

    # Новые поля
    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Отображаемое имя пользователя"
    )

    phone = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        help_text="Номер телефона пользователя"
    )

    def __str__(self):
        return f'{self.display_name or self.username} ({self.role})'