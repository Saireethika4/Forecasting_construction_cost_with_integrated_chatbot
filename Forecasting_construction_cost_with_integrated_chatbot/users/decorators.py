from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import UserRegistrationModel


def _active_user(request):
    user_id = request.session.get('id')
    return UserRegistrationModel.objects.filter(id=user_id, status='active').first() if user_id else None


def user_required(view):
    """Only logged-in active users; also rejects accounts deactivated mid-session."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = _active_user(request)
        if user is None:
            request.session.pop('id', None)
            messages.warning(request, 'Please log in to continue.')
            return redirect('UserLogin')
        request.app_user = user
        return view(request, *args, **kwargs)
    return wrapper


def user_required_json(view):
    """user_required for endpoints called from JavaScript."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = _active_user(request)
        if user is None:
            return JsonResponse({'error': 'Please log in to continue.'}, status=401)
        request.app_user = user
        return view(request, *args, **kwargs)
    return wrapper
