import json

from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone

from .models import DeliveryTask, CourierProfile, CourierApplication
from users.models import User
from orders.models import Order


def _parse_json(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def delivery_task_list(request):
    """
    Список задач доставки для текущего курьера (или админа).
    """
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    user: User | None = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    qs = DeliveryTask.objects.select_related(
        'order__shop',
        'order__client',
        'courier__user',
    )

    if user.role == User.Roles.COURIER:
        try:
            courier_profile = CourierProfile.objects.get(user=user)
        except CourierProfile.DoesNotExist:
            return JsonResponse({'detail': 'Courier profile not found'}, status=404)
        qs = qs.filter(courier=courier_profile)
    elif user.role == User.Roles.ADMIN:
        pass
    else:
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    data = []
    for task in qs.order_by('status', '-assigned_at'):
        order = task.order
        client = order.client

        # если в User нет phone — либо убери это поле, либо замени на своё
        client_phone = getattr(client, "phone", "")
        client_name = getattr(client, 'display_name', '') or client.username

        data.append(
            {
                'id': task.id,
                'order_id': task.order_id,
                'status': task.status,
                'courier_id': task.courier_id,
                'client_id': order.client_id,
                'client_username': client_name,
                'client_phone': client_phone,
                'shop_id': order.shop_id,
                'shop_name': order.shop.name,
                'delivery_address': order.delivery_address,
                'order_total_price': str(order.total_price),
                'order_created_at': order.created_at.isoformat(),
            }
        )

    return JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})


def delivery_offers_list(request):
    """
    Список свободных задач (офферы) для курьеров:
    - статус PENDING
    - courier IS NULL
    """
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    user: User | None = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    if user.role not in (User.Roles.COURIER, User.Roles.ADMIN):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    # курьер должен иметь профиль и быть активным
    if user.role == User.Roles.COURIER:
        try:
            courier_profile = CourierProfile.objects.get(user=user)
        except CourierProfile.DoesNotExist:
            return JsonResponse({"detail": "Courier profile not found"}, status=404)
        if not courier_profile.is_active:
            return JsonResponse(
                {"detail": "Courier profile is not active"},
                status=403,
            )

    qs = (
        DeliveryTask.objects
        .select_related("order__shop")
        .filter(
            status=DeliveryTask.Status.PENDING,
            courier__isnull=True,
        )
    )

    data = []
    for task in qs.order_by("-order__created_at"):
        order = task.order
        data.append(
            {
                "id": task.id,
                "order_id": order.id,
                "status": task.status,
                "shop_id": order.shop_id,
                "shop_name": order.shop.name,
                "client_id": order.client_id,
                "delivery_address": order.delivery_address,
                "order_total_price": str(order.total_price),
                "order_created_at": order.created_at.isoformat(),
            }
        )

    return JsonResponse(data, safe=False, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def delivery_task_assign(request, task_id: int):
    """
    Курьер берёт свободную задачу доставки (оффер) себе.

    Правила:
    - только роль COURIER (или ADMIN для тестов)
    - курьер должен быть активен
    - у курьера не должно быть другой активной задачи (ASSIGNED/IN_PROGRESS)
    - задача должна быть в статусе PENDING и без курьера
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    user: User | None = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    if user.role not in (User.Roles.COURIER, User.Roles.ADMIN):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    courier_profile = None
    if user.role == User.Roles.COURIER:
        try:
            courier_profile = CourierProfile.objects.get(user=user)
        except CourierProfile.DoesNotExist:
            return JsonResponse({"detail": "Courier profile not found"}, status=404)

        if not courier_profile.is_active:
            return JsonResponse(
                {"detail": "Courier profile is not active"},
                status=403,
            )

        # проверка: нет ли уже активной задачи
        has_active = DeliveryTask.objects.filter(
            courier=courier_profile,
            status__in=[
                DeliveryTask.Status.ASSIGNED,
                DeliveryTask.Status.IN_PROGRESS,
            ],
        ).exists()
        if has_active:
            return JsonResponse(
                {
                    "detail": "У вас уже есть активная задача. "
                    "Завершите её прежде чем брать новую."
                },
                status=400,
            )

    # защищаемся от гонки: два курьера одновременно жмут "Взять"
    with transaction.atomic():
        try:
            task = (
                DeliveryTask.objects
                .select_for_update()
                .select_related("order")
                .get(pk=task_id)
            )
        except DeliveryTask.DoesNotExist:
            raise Http404("Delivery task not found")

        if task.status != DeliveryTask.Status.PENDING or task.courier_id is not None:
            return JsonResponse(
                {"detail": "Task is already taken or not in PENDING status"},
                status=400,
            )

        if user.role == User.Roles.COURIER:
            task.courier = courier_profile

        task.status = DeliveryTask.Status.ASSIGNED
        task.assigned_at = timezone.now()
        task.save()

    order = task.order

    return JsonResponse(
        {
            "id": task.id,
            "status": task.status,
            "order_id": order.id,
            "courier_id": task.courier_id,
            "delivery_address": order.delivery_address,
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def delivery_task_change_status(request, task_id: int):
    if request.method != 'PATCH':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    user: User | None = request.user if request.user.is_authenticated else None
    if user is None:
        return JsonResponse({'detail': 'Authentication required'}, status=401)

    try:
        task = DeliveryTask.objects.select_related('courier__user').get(pk=task_id)
    except DeliveryTask.DoesNotExist:
        raise Http404('Delivery task not found')

    if user.role == User.Roles.COURIER:
        if task.courier is None or task.courier.user_id != user.id:
            return JsonResponse({'detail': 'Forbidden'}, status=403)
    elif user.role != User.Roles.ADMIN:
        return JsonResponse({'detail': 'Forbidden'}, status=403)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    new_status = data.get('status')
    if new_status not in DeliveryTask.Status.values:
        return JsonResponse(
            {'detail': f'Invalid status. Allowed: {list(DeliveryTask.Status.values)}'},
            status=400
        )

    task.status = new_status
    task.save()

    # синхронизируем статус заказа
    if new_status == DeliveryTask.Status.IN_PROGRESS:
        order = task.order
        order.status = Order.Status.ON_DELIVERY
        order.save()
    elif new_status == DeliveryTask.Status.DONE:
        order = task.order
        order.status = Order.Status.DELIVERED
        order.save()

    return JsonResponse(
        {
            'id': task.id,
            'status': task.status,
        },
        json_dumps_params={'ensure_ascii': False}
    )


@csrf_exempt
def courier_application_create(request):
    """
    Оставить заявку на регистрацию курьером.
    Может вызываться как залогиненным пользователем, так и гостем.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    full_name = (data.get("full_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    vehicle_type = (data.get("vehicle_type") or "").strip()
    comment = (data.get("comment") or "").strip()

    if not full_name or not phone:
        return JsonResponse(
            {"detail": "full_name и phone обязательны"},
            status=400,
        )

    user: User | None = request.user if request.user.is_authenticated else None

    app = CourierApplication.objects.create(
        user=user,
        full_name=full_name,
        phone=phone,
        vehicle_type=vehicle_type,
        comment=comment,
    )

    return JsonResponse(
        {
            "id": app.id,
            "status": app.status,
            "full_name": app.full_name,
            "phone": app.phone,
        },
        status=201,
        json_dumps_params={"ensure_ascii": False},
    )