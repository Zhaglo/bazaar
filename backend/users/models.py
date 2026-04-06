from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Расширенная модель пользователя для платформы доставки BAZAAR.

    Наследуется от стандартной модели AbstractUser Django.
    Добавляет поле role для разделения пользователей по ролям,
    а также поля display_name и phone для дополнительной информации.

    Attributes:
        role (CharField): Роль пользователя в системе.
            Возможные значения: CLIENT (клиент), SHOP (магазин/партнёр),
            COURIER (курьер), ADMIN (администратор).
        display_name (CharField): Отображаемое имя пользователя (опционально).
        phone (CharField): Номер телефона пользователя (опционально).
    """

    class Roles(models.TextChoices):
        """Допустимые роли пользователей в системе."""
        CLIENT = "CLIENT", "client"
        SHOP = "SHOP", "shop"
        COURIER = "COURIER", "courier"
        ADMIN = "ADMIN", "admin"

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.CLIENT,
    )

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
        """
        Возвращает строковое представление пользователя.

        Returns:
            str: Строка вида 'display_name (role)' или 'username (role)',
                 если display_name не задан.
        """
        return f'{self.display_name or self.username} ({self.role})'