def catalog_user(request):
    user = getattr(request, 'user', None)
    is_catalog_admin = bool(
        user and user.is_authenticated and user.is_catalog_admin()
    )
    return {'is_catalog_admin': is_catalog_admin}
