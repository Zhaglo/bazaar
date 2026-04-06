import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import User


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
def login_view(request):
    """
    Аутентифицирует пользователя и выполняет вход (login).

    Ожидает POST-запрос с JSON-телом, содержащим поля:
        - username (str): Имя пользователя.
        - password (str): Пароль.

    При успешном входе создаёт сессию и возвращает данные пользователя.

    HTTP метод: POST

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse:
            - При успехе: данные пользователя (id, username, role, display_name, phone) с HTTP 200.
            - При ошибке: сообщение об ошибке с соответствующим HTTP-статусом.

    Возможные ошибки:
        405: Не POST-запрос.
        400: Отсутствует JSON или не указаны username/password.
        401: Неверные учётные данные.
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return JsonResponse({'detail': 'Username and password are required'}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({'detail': 'Invalid credentials'}, status=401)

    login(request, user)

    return JsonResponse(
        {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'display_name': user.display_name,
            'phone': user.phone,
        },
        json_dumps_params={'ensure_ascii': False},
    )


@csrf_exempt
def logout_view(request):
    """
    Выполняет выход пользователя из системы (logout).

    Завершает текущую сессию.

    HTTP метод: POST

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse: Сообщение {'detail': 'Logged out'} с HTTP 200.

    Возможные ошибки:
        405: Не POST-запрос.
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    logout(request)

    return JsonResponse({'detail': 'Logged out'}, json_dumps_params={'ensure_ascii': False})


def me_view(request):
    """
    Возвращает информацию о текущем аутентифицированном пользователе.

    Доступ: только для авторизованных пользователей.

    HTTP метод: GET (по умолчанию, но можно разрешить и другие – здесь явно не ограничено)

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse:
            - При успехе: данные пользователя (id, username, role, display_name, phone) с HTTP 200.
            - При отсутствии авторизации: {'detail': 'Not authenticated'} с HTTP 401.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Not authenticated'}, status=401)

    user: User = request.user  # type: ignore

    return JsonResponse(
        {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'display_name': user.display_name,
            'phone': user.phone,
        }, json_dumps_params={'ensure_ascii': False},
    )


@csrf_exempt
def register_view(request):
    """
    Регистрирует нового пользователя (клиента) в системе.

    Ожидает POST-запрос с JSON-телом, содержащим поля:
        - username (str, обязательное): Имя пользователя.
        - password (str, обязательное): Пароль.
        - password2 (str, обязательное): Подтверждение пароля.
        - email (str, опционально): Адрес электронной почты.
        - display_name (str, опционально): Отображаемое имя.
        - phone (str, опционально): Номер телефона.

    Пользователю автоматически назначается роль CLIENT (по умолчанию).

    HTTP метод: POST

    Args:
        request (HttpRequest): Объект запроса.

    Returns:
        JsonResponse:
            - При успехе: данные созданного пользователя (id, username, email, role, display_name, phone) с HTTP 201.
            - При ошибке: сообщение об ошибке с HTTP 400, 405.

    Возможные ошибки:
        405: Не POST-запрос.
        400: Неверный JSON, отсутствуют обязательные поля, пароли не совпадают,
             или пользователь с таким username уже существует.
    """
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    data = _parse_json(request)
    if data is None:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    password2 = data.get('password2') or ''
    email = (data.get('email') or '').strip()

    display_name = (data.get('display_name') or '').strip()
    phone = (data.get('phone') or '').strip()

    if not username or not password or not password2:
        return JsonResponse(
            {'detail': 'username, password и password2 обязательны'},
            status=400,
        )

    if password != password2:
        return JsonResponse({'detail': 'Пароли не совпадают'}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse(
            {'detail': 'Пользователь с таким именем уже существует'},
            status=400,
        )

    user = User.objects.create_user(
        username=username,
        email=email or None,
        password=password,
    )

    if display_name:
        user.display_name = display_name
    if phone:
        user.phone = phone
    # роль по умолчанию = CLIENT из модели
    user.save()

    return JsonResponse(
        {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'display_name': user.display_name,
            'phone': user.phone,
        },
        status=201,
        json_dumps_params={'ensure_ascii': False},
    )