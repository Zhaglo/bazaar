import json
from decimal import Decimal

from django.db import transaction
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from users.models import User
from orders.models import Order, OrderItem
from shops.models import Shop, CatalogItem
from delivery.models import DeliveryTask


def _parse_json(request):
    """
    Извлекает и декодирует JSON из тела HTTP-запроса.

    Args:
        request (HttpRequest): Объект HTTP-запроса Django.

    Returns:
        dict | None: Словарь, полученный из JSON, или None, если JSON некорректен.
    """
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


@csrf_exempt
def order_list_or_create(request):
    """
    Обрабатывает GET и POST запросы для списка заказов и создания нового заказа.

    GET:
        Возвращает список заказов в зависимости от роли пользователя:
            - Клиент: только свои заказы.
            - Магазин (партнёр): заказы своего магазина.
            - Курьер: заказы, назначенные ему на доставку.
            - Администратор: все заказы.

    POST:
        Создаёт новый заказ от имени клиента.
        Требует авторизации и роль CLIENT.
        Тело запроса должно содержать JSON с полями:
            - shop_id (int): ID магазина.
            - delivery_address (str): Адрес доставки.
            - items (list): Список позиций, каждая с catalog_item_id и quantity (опционально, по умолчанию 1).

    HTTP методы: GET, POST

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse: Для GET – список заказов с деталями позиций.
                      Для POST – данные созданного заказа (статус 201).
    """
    user: User | None = request.user if request.user.is_authenticated else None

    if request.method == 'GET':
        if user is None:
            return JsonResponse({'detail': 'Authentication required'}, status=401)

        qs = Order.objects.select_related('client', 'shop').prefetch_related('items__catalog_item').all()

        if user.role == User.Roles.CLIENT:
            qs = qs.filter(client=user)
        elif user.role == User.Roles.SHOP:
            qs = qs.filter(shop__owner=user)
        elif user.role == User.Roles.COURIER:
            qs = qs.filter(delivery_task__courier__user=user)
        else:
            pass # Админ видит всё

        data = []
        for order in qs.order_by('-created_at'):
            items_data = []
            for item in order.items.all():
                items_data.append(
                    {
                        'id': item.id,
                        'catalog_item_id': item.catalog_item_id,
                        'name': item.catalog_item.name,
                        'quantity': item.quantity,
                        'price': str(item.price_at_moment),
                        'line_total': str(item.get_total()),
                    }
                )
            data.append(
                {
                    'id': order.id,
                    'status': order.status,
                    'client_id': order.client_id,
                    'shop_id': order.shop_id,
                    'shop_name': order.shop.name,
                    'delivery_address': order.delivery_address,
                    'total_price': str(order.total_price),
                    'created_at': order.created_at.isoformat(),
                    'items': items_data,
                }
            )
        return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})

    if request.method == 'POST':
        return _order_create(request, user)

    return JsonResponse({'detail': 'Method not allowed'}, status=405)


def _order_create(request, user: User | None):
    """
    Внутренняя функция для создания заказа (вызывается из order_list_or_create при POST).

    Выполняет:
        - Проверку аутентификации и роли CLIENT.
        - Валидацию входных данных (shop_id, delivery_address, items).
        - Создание заказа и позиций в атомарной транзакции.
        - Подсчёт общей суммы заказа.

    Args:
        request (HttpRequest): Объект запроса.
        user (User | None): Аутентифицированный пользователь (клиент).

    Returns:
        JsonResponse: Данные созданного заказа (статус 201) или ошибка.
    """
    if user is None or not request.user.is_authenticated:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    if user.role != User.Roles.CLIENT:
        return JsonResponse({'detail': 'Only clients can create orders'}, status=403)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    required_fields = ['shop_id', 'delivery_address', 'items']
    for field in required_fields:
        if field not in data:
            return JsonResponse({'detail': f'Missing field: {field}'}, status=400)

    shop_id = data['shop_id']
    delivery_address = data['delivery_address']
    items_data = data['items']

    if not isinstance(items_data, list) or not items_data:
        return JsonResponse({'detail': 'Items must be a non-empty list'}, status=400)

    try:
        shop = Shop.objects.get(pk=shop_id)
    except Shop.DoesNotExist:
        return JsonResponse({'detail': 'Shop not found'}, status=404)

    with transaction.atomic():
        order = Order.objects.create(
            client=user,
            shop=shop,
            delivery_address=delivery_address,
            status=Order.Status.NEW,
            total_price=Decimal("0.00"),
        )

        total_price = Decimal("0.00")
        items_response = []

        for item in items_data:
            try:
                catalog_item_id = item['catalog_item_id']
                quantity = int(item.get('quantity', 1))
            except (KeyError, ValueError, TypeError):
                transaction.set_rollback(True)
                return JsonResponse({'detail': 'Invalid item format'}, status=400)

            if quantity <= 0:
                transaction.set_rollback(True)
                return JsonResponse({'detail': 'Quantity must be positive'}, status=400)

            try:
                catalog_item = CatalogItem.objects.get(pk=catalog_item_id, shop=shop)
            except CatalogItem.DoesNotExist:
                transaction.set_rollback(True)
                return JsonResponse(
                    {'detail': f'Catalog item {catalog_item_id} not found for this shop'},
                    status=404
                )

            price = catalog_item.price
            line_total = price * quantity
            total_price += line_total

            order_item = OrderItem.objects.create(
                order=order,
                catalog_item=catalog_item,
                quantity=quantity,
                price_at_moment=price,
            )

            items_response.append(
                {
                    'id': order_item.id,
                    'catalog_item_id': catalog_item.id,
                    'name': catalog_item.name,
                    'quantity': quantity,
                    'price': str(price),
                    'line_total': str(line_total),
                }
            )

        order.total_price = total_price
        order.save()

    return JsonResponse(
        {
            'id': order.id,
            'status': order.status,
            'client_id': order.client.id,
            'shop_id': order.shop.id,
            'shop_name': order.shop.name,
            'delivery_address': order.delivery_address,
            'total_price': str(order.total_price),
            'created_at': order.created_at.isoformat(),
            'items': items_response,
        },
        status=201,
        json_dumps_params={'ensure_ascii': False}
    )


@login_required
def order_detail(request, order_id: int):
    """
    Возвращает детальную информацию о конкретном заказе.

    Доступ:
        - Клиент: только свои заказы.
        - Магазин (партнёр): заказы своего магазина.
        - Курьер: заказы, назначенные ему (через delivery_task).
        - Администратор: любые заказы.

    HTTP метод: GET

    Args:
        request (HttpRequest): Объект запроса.
        order_id (int): Идентификатор заказа.

    Returns:
        JsonResponse: Данные заказа с позициями (товары, цены, адрес).

    Raises:
        404: Заказ не найден.
        403: Доступ запрещён (роль не позволяет просматривать этот заказ).
        405: Не GET-запрос.
    """
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    try:
        order = (
            Order.objects
            .select_related('client', 'shop')
            .prefetch_related('items__catalog_item')
            .get(pk=order_id)
        )
    except Order.DoesNotExist:
        raise Http404('Order not found')

    user: User = request.user

    if user.role != User.Roles.ADMIN:
        if user.role == User.Roles.CLIENT and order.client_id != user.id:
            return JsonResponse({'detail': 'Forbidden'}, status=403)

        if user.role == User.Roles.SHOP and order.shop.owner_id != user.id:
            return JsonResponse({'detail': 'Forbidden'}, status=403)

        if user.role == User.Roles.COURIER:
            # у заказа может не быть задачи доставки или курьера
            if not hasattr(order, 'delivery_task') or order.delivery_task.courier is None:
                return JsonResponse({'detail': 'Forbidden'}, status=403)
            if order.delivery_task.courier.user_id != user.id:
                return JsonResponse({'detail': 'Forbidden'}, status=403)

    items_response = []
    for item in order.items.all():
        items_response.append(
            {
                'id': item.id,
                'catalog_item_id': item.catalog_item.id,
                'name': item.catalog_item.name,
                'quantity': item.quantity,
                'price': str(item.price_at_moment),
                'line_total': str(item.get_total()),
            }
        )

    return JsonResponse(
        {
            'id': order.id,
            'status': order.status,
            'client_id': order.client.id,
            'shop_id': order.shop.id,
            'shop_name': order.shop.name,
            'shop_address': order.shop.address,
            'delivery_address': order.delivery_address,
            'total_price': str(order.total_price),
            'created_at': order.created_at.isoformat(),
            'items': items_response,
        },
        json_dumps_params={'ensure_ascii': False}
    )


@csrf_exempt
def order_change_status(request, order_id: int):
    """
    Изменяет статус заказа.

    Доступ:
        - Магазин (партнёр): только для своих заказов.
        - Администратор: для любых заказов.

    Особое поведение:
        При переводе заказа в статус ON_DELIVERY автоматически создаётся (или получается существующая)
        задача доставки (DeliveryTask) со статусом PENDING.

    HTTP метод: PATCH

    Args:
        request (HttpRequest): Объект запроса. Тело должно содержать JSON с ключом 'status'.
        order_id (int): Идентификатор заказа.

    Returns:
        JsonResponse: Обновлённый id и status заказа.

    Raises:
        401: Пользователь не аутентифицирован.
        403: Недостаточно прав (не свой магазин и не админ).
        404: Заказ не найден.
        400: Неверный JSON или недопустимое значение статуса.
        405: Не PATCH-запрос.
    """
    if request.method != 'PATCH':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    user: User | None = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    try:
        order = Order.objects.select_related('shop__owner').get(pk=order_id)
    except Order.DoesNotExist:
        raise Http404('Order not found')

    if user.role not in (User.Roles.SHOP, User.Roles.ADMIN):
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    if user.role == User.Roles.SHOP and order.shop.owner_id != user.id:
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    new_status = data.get('status')
    if new_status not in Order.Status.values:
        return JsonResponse(
            {'detail': f'Invalid status. Allowed: {list(Order.Status.values)}'},
            status=400
        )

    order.status = new_status
    order.save()

    if new_status == Order.Status.ON_DELIVERY:
        task, created = DeliveryTask.objects.get_or_create(
            order=order,
            defaults={
                "status": DeliveryTask.Status.PENDING,
            },
        )

    return JsonResponse(
        {
            'id': order.id,
            'status': order.status,
        },
        json_dumps_params={'ensure_ascii': False}
    )
