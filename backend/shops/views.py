import json
from decimal import Decimal
from datetime import timedelta, date

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, Http404
from django.utils import timezone
from django.db.models import Count, Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import TruncDate, ExtractWeekDay

from .models import Shop, CatalogItem, CatalogSection, ShopApplication
from orders.models import Order, OrderItem
from users.models import User


def _parse_json(request):
    """
    Извлекает и декодирует JSON из тела HTTP-запроса.

    Args:
        request (HttpRequest): Объект HTTP-запроса Django.

    Returns:
        dict | None: Словарь, полученный из JSON, или None, если JSON некорректен.
    """
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def shop_list(request):
    """
    Возвращает список всех магазинов, зарегистрированных на платформе.

    Доступ: публичный (без авторизации).

    HTTP метод: GET

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse: Список магазинов с полями id, name, address, description.
    """
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    shops = Shop.objects.all().values('id', 'name', 'address', 'description')
    return JsonResponse(list(shops), safe=False, json_dumps_params={'ensure_ascii': False})


def shop_catalog(request, shop_id):
    """
    Возвращает каталог товаров указанного магазина.

    Доступ: публичный (без авторизации).

    HTTP метод: GET

    Args:
        request (HttpRequest): Объект запроса.
        shop_id (int): Идентификатор магазина.

    Returns:
        JsonResponse: Объект с полями shop (id, name, address) и catalog (список товаров).

    Raises:
        404: Магазин не найден.
    """
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    try:
        shop = Shop.objects.get(pk=shop_id)
    except Shop.DoesNotExist:
        raise Http404('Shop not found')

    items = shop.catalog_items.all().values(
        'id', 'name', 'description', 'price', 'section_id', 'is_available'
    )

    return JsonResponse(
        {
            'shop': {
                'id': shop.id,
                'name': shop.name,
                'address': shop.address,
            },
            'catalog': list(items),
        },
        safe=False,
        json_dumps_params={'ensure_ascii': False}
    )


@csrf_exempt
def shop_application_create(request):
    """
    Создаёт заявку на регистрацию нового магазина.

    Может вызываться как авторизованным пользователем, так и гостем.

    Обязательные поля в JSON:
        - shop_name (str): Название магазина.
        - address (str): Адрес магазина.
        - contact_name (str): Контактное лицо.
        - contact_phone (str): Телефон для связи.

    Опциональные поля:
        - description (str): Описание магазина.
        - comment (str): Дополнительный комментарий.

    HTTP метод: POST

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse: Данные созданной заявки (id, status, shop_name, contact_name, contact_phone) с HTTP 201.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    shop_name = (data.get("shop_name") or "").strip()
    address = (data.get("address") or "").strip()
    description = (data.get("description") or "").strip()
    contact_name = (data.get("contact_name") or "").strip()
    contact_phone = (data.get("contact_phone") or "").strip()
    comment = (data.get("comment") or "").strip()

    if not shop_name or not address or not contact_name or not contact_phone:
        return JsonResponse(
            {"detail": "shop_name, address, contact_name и contact_phone обязательны"},
            status=400,
        )

    user: User | None = request.user if request.user.is_authenticated else None

    app = ShopApplication.objects.create(
        user=user,
        shop_name=shop_name,
        address=address,
        description=description,
        contact_name=contact_name,
        contact_phone=contact_phone,
        comment=comment,
    )

    return JsonResponse(
        {
            "id": app.id,
            "status": app.status,
            "shop_name": app.shop_name,
            "contact_name": app.contact_name,
            "contact_phone": app.contact_phone,
        },
        status=201,
        json_dumps_params={"ensure_ascii": False},
    )


@login_required
def my_shops(request):
    """
    Возвращает список магазинов, принадлежащих текущему пользователю.

    Доступ:
        - Пользователь с ролью SHOP (владелец магазина).
        - Администратор (видит все свои магазины, если создавал).

    HTTP метод: GET

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse: Список магазинов с полями id, name, address, description.

    Raises:
        403: Пользователь не имеет роли SHOP или ADMIN.
    """
    user: User = request.user  # type: ignore

    if user.role not in (User.Roles.SHOP, User.Roles.ADMIN):
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    qs = Shop.objects.filter(owner=user).values(
        'id', 'name', 'address', 'description'
    )

    return JsonResponse(list(qs), safe=False, json_dumps_params={'ensure_ascii': False})


@login_required
@csrf_exempt
def shop_catalog_manage(request, shop_id: int):
    """
    Управление каталогом магазина: создание нового товара.

    Доступ:
        - Владелец магазина (роль SHOP).
        - Администратор.

    HTTP метод: POST

    Тело запроса (JSON):
        - name (str, обязательное): Название товара.
        - price (decimal, обязательное): Цена.
        - description (str, опционально): Описание.
        - is_available (bool, опционально, по умолчанию True): Доступность.
        - section_id (int, опционально): ID раздела каталога.

    Args:
        request (HttpRequest): Объект запроса.
        shop_id (int): ID магазина.

    Returns:
        JsonResponse: Данные созданного товара (id, section_id, name, description, price, is_available) с HTTP 201.

    Raises:
        403: Недостаточно прав или магазин не принадлежит пользователю.
        404: Магазин или раздел не найден.
        400: Некорректные данные (отсутствуют обязательные поля, неверная цена).
    """
    user: User = request.user  # type: ignore

    if user.role not in (User.Roles.SHOP, User.Roles.ADMIN):
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    try:
        shop = Shop.objects.get(pk=shop_id)
    except Shop.DoesNotExist:
        return JsonResponse({'detail': 'Shop not found'}, status=404)

    if user.role == User.Roles.SHOP and shop.owner_id != user.id:
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    price_raw = data.get('price')
    is_available = bool(data.get('is_available', True))
    section_id = data.get('section_id')

    if not name or price_raw is None:
        return JsonResponse({'detail': 'name и price обязательны'}, status=400)

    try:
        price = Decimal(str(price_raw))
    except Exception:
        return JsonResponse({'detail': 'Некорректная цена'}, status=400)

    section = None
    if section_id is not None:
        try:
            section = CatalogSection.objects.get(pk=section_id, shop=shop)
        except CatalogSection.DoesNotExist:
            return JsonResponse({'detail': 'Section not found'}, status=404)

    item = CatalogItem.objects.create(
        shop=shop,
        section=section,
        name=name,
        description=description,
        price=price,
        is_available=is_available,
    )

    return JsonResponse(
        {
            'id': item.id,
            'section_id': item.section_id,
            'name': item.name,
            'description': item.description,
            'price': str(item.price),
            'is_available': item.is_available,
        },
        status=201,
        json_dumps_params={'ensure_ascii': False},
    )


@login_required
@csrf_exempt
def shop_catalog_item_manage(request, shop_id: int, item_id: int):
    """
    Управление конкретным товаром каталога: обновление (PATCH) или удаление (DELETE).

    Доступ:
        - Владелец магазина (роль SHOP).
        - Администратор.

    HTTP методы:
        - PATCH: обновление полей товара (name, description, price, is_available, section_id).
        - DELETE: удаление товара.

    Args:
        request (HttpRequest): Объект запроса.
        shop_id (int): ID магазина.
        item_id (int): ID товара.

    Returns:
        JsonResponse: При PATCH – обновлённые данные товара.
                      При DELETE – {"detail": "Deleted"}.

    Raises:
        403: Недостаточно прав.
        404: Магазин или товар не найден.
        400: Некорректные данные (неверный JSON или цена).
    """
    user: User = request.user  # type: ignore

    if user.role not in (User.Roles.SHOP, User.Roles.ADMIN):
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    try:
        shop = Shop.objects.get(pk=shop_id)
    except Shop.DoesNotExist:
        return JsonResponse({'detail': 'Shop not found'}, status=404)

    if user.role == User.Roles.SHOP and shop.owner_id != user.id:
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    try:
        item = CatalogItem.objects.get(pk=item_id, shop=shop)
    except CatalogItem.DoesNotExist:
        return JsonResponse({'detail': 'Catalog item not found'}, status=404)

    if request.method == 'DELETE':
        item.delete()
        return JsonResponse({'detail': 'Deleted'}, status=200)

    if request.method == 'PATCH':
        data = _parse_json(request)
        if data is None:
            return JsonResponse({'detail': 'Invalid JSON'}, status=400)

        if 'name' in data:
            item.name = (data['name'] or '').strip()
        if 'description' in data:
            item.description = (data['description'] or '').strip()
        if 'is_available' in data:
            item.is_available = bool(data['is_available'])
        if 'price' in data:
            try:
                item.price = Decimal(str(data['price']))
            except Exception:
                return JsonResponse({'detail': 'Некорректная цена'}, status=400)
        if 'section_id' in data:
            section_id = data['section_id']
            if section_id is None:
                item.section = None
            else:
                try:
                    section = CatalogSection.objects.get(pk=section_id, shop=shop)
                except CatalogSection.DoesNotExist:
                    return JsonResponse({'detail': 'Section not found'}, status=404)
                item.section = section

        item.save()

        return JsonResponse(
            {
                'id': item.id,
                'section_id': item.section_id,
                'name': item.name,
                'description': item.description,
                'price': str(item.price),
                'is_available': item.is_available,
            },
            json_dumps_params={'ensure_ascii': False},
        )

    return JsonResponse({'detail': 'Method not allowed'}, status=405)


@login_required
@csrf_exempt
def shop_sections_manage(request, shop_id: int):
    """
    Управление разделами каталога магазина.

    Доступ:
        - Владелец магазина (роль SHOP).
        - Администратор.

    HTTP методы:
        - GET: список разделов магазина.
        - POST: создание нового раздела.

    При POST:
        Обязательное поле: name (str).
        Опциональное поле: ordering (int, по умолчанию 0).

    Args:
        request (HttpRequest): Объект запроса.
        shop_id (int): ID магазина.

    Returns:
        JsonResponse: При GET – список разделов (id, name, ordering).
                      При POST – данные созданного раздела с HTTP 201.

    Raises:
        403: Недостаточно прав.
        404: Магазин не найден.
        400: Некорректные данные (отсутствует name).
    """
    user: User = request.user  # type: ignore

    if user.role not in (User.Roles.SHOP, User.Roles.ADMIN):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    try:
        shop = Shop.objects.get(pk=shop_id)
    except Shop.DoesNotExist:
        return JsonResponse({"detail": "Shop not found"}, status=404)

    if user.role == User.Roles.SHOP and shop.owner_id != user.id:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    if request.method == "GET":
        sections = shop.catalog_sections.all().values("id", "name", "ordering")
        return JsonResponse(list(sections), safe=False, json_dumps_params={"ensure_ascii": False})

    if request.method == "POST":
        data = _parse_json(request)
        if data is None:
            return JsonResponse({"detail": "Invalid JSON"}, status=400)

        name = (data.get("name") or "").strip()
        ordering = data.get("ordering") or 0

        if not name:
            return JsonResponse({"detail": "name обязателен"}, status=400)

        section = CatalogSection.objects.create(
            shop=shop,
            name=name,
            ordering=ordering,
        )

        return JsonResponse(
            {"id": section.id, "name": section.name, "ordering": section.ordering},
            status=201,
            json_dumps_params={"ensure_ascii": False},
        )

    return JsonResponse({"detail": "Method not allowed"}, status=405)


@login_required
@csrf_exempt
def shop_section_item_manage(request, shop_id: int, section_id: int):
    """
    Управление конкретным разделом каталога: обновление (PATCH) или удаление (DELETE).

    Доступ:
        - Владелец магазина (роль SHOP).
        - Администратор.

    HTTP методы:
        - PATCH: обновление полей раздела (name, ordering).
        - DELETE: удаление раздела. Товары, привязанные к разделу, получают section = NULL (не удаляются).

    Args:
        request (HttpRequest): Объект запроса.
        shop_id (int): ID магазина.
        section_id (int): ID раздела.

    Returns:
        JsonResponse: При PATCH – обновлённые данные раздела.
                      При DELETE – {"detail": "Deleted"}.

    Raises:
        403: Недостаточно прав.
        404: Магазин или раздел не найден.
        400: Некорректные данные (неверный JSON).
    """
    user: User = request.user  # type: ignore

    if user.role not in (User.Roles.SHOP, User.Roles.ADMIN):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    try:
        shop = Shop.objects.get(pk=shop_id)
    except Shop.DoesNotExist:
        return JsonResponse({"detail": "Shop not found"}, status=404)

    if user.role == User.Roles.SHOP and shop.owner_id != user.id:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    try:
        section = CatalogSection.objects.get(pk=section_id, shop=shop)
    except CatalogSection.DoesNotExist:
        return JsonResponse({"detail": "Section not found"}, status=404)

    if request.method == "DELETE":
        CatalogItem.objects.filter(section=section).update(section=None)
        section.delete()
        return JsonResponse({"detail": "Deleted"}, status=200)

    if request.method == "PATCH":
        data = _parse_json(request)
        if data is None:
            return JsonResponse({"detail": "Invalid JSON"}, status=400)

        if "name" in data:
            section.name = (data["name"] or "").strip()
        if "ordering" in data:
            section.ordering = int(data["ordering"] or 0)
        section.save()

        return JsonResponse(
            {"id": section.id, "name": section.name, "ordering": section.ordering},
            json_dumps_params={"ensure_ascii": False},
        )

    return JsonResponse({"detail": "Method not allowed"}, status=405)


@login_required
def shop_stats(request, shop_id: int):
    """
    Возвращает расширенную статистику по заказам магазина.

    Доступ:
        - Владелец магазина (роль SHOP).
        - Администратор.

    Параметры запроса (GET):
        - period (str, опционально): today | 7d | 30d | all. По умолчанию 7d.

    Возвращаемые данные:
        - period, from, to – период статистики.
        - totals: общее число заказов, доставленных, отменённых, выручка, средний чек.
        - status_counts: количество заказов по каждому статусу.
        - top_items: топ-10 товаров по количеству продаж и выручке.
        - by_day: динамика заказов и выручки по дням.
        - orders_by_weekday: распределение по дням недели.

    Args:
        request (HttpRequest): Объект запроса.
        shop_id (int): ID магазина.

    Returns:
        JsonResponse: Объект со статистикой.

    Raises:
        403: Недостаточно прав.
        404: Магазин не найден.
    """
    user: User = request.user  # type: ignore

    if user.role not in (User.Roles.SHOP, User.Roles.ADMIN):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    try:
        shop = Shop.objects.get(pk=shop_id)
    except Shop.DoesNotExist:
        return JsonResponse({"detail": "Shop not found"}, status=404)

    if user.role == User.Roles.SHOP and shop.owner_id != user.id:
        return JsonResponse({"detail": "Forbidden"}, status=403)

    period = request.GET.get("period", "7d")  # today | 7d | 30d | all
    now = timezone.now()
    start = None

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        start = now - timedelta(days=7)
    elif period == "30d":
        start = now - timedelta(days=30)
    elif period == "all":
        start = None
    else:
        start = now - timedelta(days=7)

    qs = Order.objects.filter(shop=shop)
    if start is not None:
        qs = qs.filter(created_at__gte=start)

    total_orders = qs.count()
    delivered_qs = qs.filter(status=Order.Status.DELIVERED)
    cancelled_qs = qs.filter(status=Order.Status.CANCELLED)
    non_cancelled_qs = qs.exclude(status=Order.Status.CANCELLED)

    delivered_count = delivered_qs.count()
    cancelled_count = cancelled_qs.count()

    revenue_agg = non_cancelled_qs.aggregate(total=Sum("total_price"))
    revenue: Decimal = revenue_agg["total"] or Decimal("0.00")

    non_cancelled_count = non_cancelled_qs.count()
    if non_cancelled_count > 0:
        avg_check = (revenue / non_cancelled_count).quantize(Decimal("0.01"))
    else:
        avg_check = Decimal("0.00")

    status_counts_raw = (
        qs.values("status")
        .annotate(count=Count("id"))
        .order_by()
    )
    all_statuses = [s for s, _ in Order.Status.choices]
    status_counts: dict[str, int] = {s: 0 for s in all_statuses}
    for row in status_counts_raw:
        status_counts[row["status"]] = row["count"]

    items_qs = (
        OrderItem.objects
        .filter(order__shop=shop)
        .exclude(order__status=Order.Status.CANCELLED)
    )
    if start is not None:
        items_qs = items_qs.filter(order__created_at__gte=start)

    items_qs = items_qs.annotate(
        line_total=ExpressionWrapper(
            F("price_at_moment") * F("quantity"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    )

    top_items_raw = (
        items_qs
        .values("catalog_item_id", "catalog_item__name")
        .annotate(
            quantity=Sum("quantity"),
            revenue=Sum("line_total"),
        )
        .order_by("-quantity")[:10]
    )

    top_items = [
        {
            "catalog_item_id": row["catalog_item_id"],
            "name": row["catalog_item__name"],
            "quantity": row["quantity"],
            "revenue": str(row["revenue"] or Decimal("0.00")),
        }
        for row in top_items_raw
    ]

    by_day_raw = (
        non_cancelled_qs
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            orders_count=Count("id"),
            revenue=Sum("total_price"),
        )
        .order_by("day")
    )

    by_day = [
        {
            "date": row["day"].isoformat() if isinstance(row["day"], date) else str(row["day"]),
            "orders_count": row["orders_count"],
            "revenue": str(row["revenue"] or Decimal("0.00")),
        }
        for row in by_day_raw
    ]

    weekday_raw = (
        non_cancelled_qs
        .annotate(dow=ExtractWeekDay("created_at"))  # 1..7
        .values("dow")
        .annotate(
            orders_count=Count("id"),
            revenue=Sum("total_price"),
        )
        .order_by("dow")
    )

    weekday_labels = {
        1: "Вс",
        2: "Пн",
        3: "Вт",
        4: "Ср",
        5: "Чт",
        6: "Пт",
        7: "Сб",
    }

    orders_by_weekday = []
    for row in weekday_raw:
        dow = row["dow"] or 0
        orders_by_weekday.append(
            {
                "weekday": int(dow),
                "weekday_display": weekday_labels.get(int(dow), str(dow)),
                "orders_count": row["orders_count"],
                "revenue": str(row["revenue"] or Decimal("0.00")),
            }
        )

    resp = {
        "period": period,
        "from": start.isoformat() if start else None,
        "to": now.isoformat(),
        "totals": {
            "orders_count": total_orders,
            "delivered_count": delivered_count,
            "cancelled_count": cancelled_count,
            "revenue": str(revenue),
            "avg_check": str(avg_check),
        },
        "status_counts": status_counts,
        "top_items": top_items,
        "by_day": by_day,
        "orders_by_weekday": orders_by_weekday,
    }

    return JsonResponse(resp, json_dumps_params={"ensure_ascii": False})
