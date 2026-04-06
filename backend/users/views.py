import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import User


def _parse_json(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return None


@csrf_exempt
def login_view(request):
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
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    logout(request)

    return JsonResponse({'detail': 'Logged out'}, json_dumps_params={'ensure_ascii': False})


def me_view(request):
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