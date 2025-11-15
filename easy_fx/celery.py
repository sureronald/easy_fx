import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'easy_fx.settings')

app = Celery('easy_fx')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
