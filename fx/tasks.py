from celery import shared_task
from .services import update_all_exchange_rates


@shared_task(name='fx.update_exchange_rates')
def update_exchange_rates():
    """
    Celery task to update exchange rates for all active currencies.
    """
    update_all_exchange_rates()
