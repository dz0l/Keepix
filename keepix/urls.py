from django.urls import include, path


urlpatterns = [
    path('', include(('apps.core.urls', 'core'), namespace='core')),
    path('accounts/', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),
]
