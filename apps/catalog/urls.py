from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('objects/', views.object_list, name='object_list'),
    path('objects/new/', views.object_create, name='object_create'),
    path('objects/qr-search/', views.qr_search, name='qr_search'),
    path('objects/<str:code>/', views.object_detail, name='object_detail'),
    path('objects/<str:code>/edit/', views.object_edit, name='object_edit'),
    path('objects/<str:code>/delete/', views.object_delete, name='object_delete'),
    path('objects/<str:code>/qr.png', views.object_qr, name='object_qr'),
    path(
        'objects/<str:code>/photos/<int:photo_id>/delete/',
        views.photo_delete,
        name='photo_delete',
    ),
    path(
        'objects/<str:code>/photos/<int:photo_id>/primary/',
        views.photo_set_primary,
        name='photo_set_primary',
    ),
    path(
        'objects/<str:code>/pdfs/<int:pdf_id>/delete/',
        views.pdf_delete,
        name='pdf_delete',
    ),
]
