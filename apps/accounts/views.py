from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils import timezone

from django.conf import settings

from apps.accounts.forms import LoginForm
from apps.accounts.models import User


def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']

        locked_user = User.objects.filter(username=username).first()
        if locked_user and locked_user.locked_until and locked_user.locked_until > timezone.now():
            messages.error(request, 'Учётная запись временно заблокирована. Повторите позже.')
            return render(request, 'accounts/login.html', {'form': form})

        candidate = authenticate(request, username=username, password=password)
        user_obj = User.objects.filter(username=username).first()

        if candidate is None:
            if user_obj:
                user_obj.failed_login_attempts += 1
                changed = ['failed_login_attempts']
                if user_obj.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                    from datetime import timedelta

                    user_obj.locked_until = timezone.now() + timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
                    user_obj.failed_login_attempts = 0
                    changed.append('locked_until')
                user_obj.save(update_fields=changed)
            messages.error(request, 'Неверный логин или пароль.')
            return render(request, 'accounts/login.html', {'form': form})

        if not candidate.is_active:
            messages.error(request, 'Учётная запись отключена.')
            return render(request, 'accounts/login.html', {'form': form})

        candidate.failed_login_attempts = 0
        candidate.locked_until = None
        candidate.save(update_fields=['failed_login_attempts', 'locked_until'])

        login(request, candidate)
        return redirect(settings.LOGIN_REDIRECT_URL)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)
