from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('objects/', views.object_list, name='object_list'),
    path('objects/new/', views.object_create, name='object_create'),
    path('objects/<str:code>/', views.object_detail, name='object_detail'),
    path('objects/<str:code>/edit/', views.object_edit, name='object_edit'),
    path('objects/<str:code>/delete/', views.object_delete, name='object_delete'),
]
