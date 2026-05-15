from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('health/live/', views.health_live, name='health_live'),
    path('health/ready/', views.health_ready, name='health_ready'),
    path('attachments/pdf/<int:pk>/', views.download_pdf_attachment, name='download_pdf_attachment'),
    path('media/<path:rel_path>', views.accel_media, name='media_accel'),
]
