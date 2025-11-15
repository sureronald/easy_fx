"""
URL configuration for easy_fx project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('fx/', include('fx.urls')),
    path('', include('django_prometheus.urls')),
]
