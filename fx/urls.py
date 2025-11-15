from django.urls import path
from .views import QuoteViewSet, health_check, readiness_check, demo_page

urlpatterns = [
    path('', QuoteViewSet.as_view({'post': 'create'}), name='quote-create'),
    path('<uuid:pk>/', QuoteViewSet.as_view({'get': 'retrieve'}), name='quote-retrieve'),
    path('health/', health_check, name='health-check'),
    path('ready/', readiness_check, name='readiness-check'),
    path('demo/', demo_page, name='demo-page'),
]
