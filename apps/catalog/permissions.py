from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def catalog_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_catalog_admin():
            messages.error(request, 'Недостаточно прав для этого действия.')
            return redirect('catalog:object_list')
        return view_func(request, *args, **kwargs)

    return wrapper
