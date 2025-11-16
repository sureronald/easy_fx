import logging
import json
import requests
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from .models import Currency, Rate

logger = logging.getLogger('fx')


def should_refresh_rates() -> bool:
    """Check if rates need to be refreshed based on EXCHANGE_RATES_REFRESH setting."""
    refresh_interval = settings.EXCHANGE_RATES_REFRESH

    # Check if any rate exists and get the most recent one
    latest_rate = Rate.objects.order_by('-last_updated').first()

    if not latest_rate:
        return True

    time_since_update = (timezone.now() - latest_rate.last_updated).total_seconds()
    return time_since_update >= refresh_interval


def fetch_rates_for_currency(base_currency, target_currencies) -> dict:
    """
    Fetch exchange rates from the API for a given base currency.

    Args:
        base_currency: Currency object to use as base
        target_currencies: List of Currency codes to get rates for

    Returns:
        dict: Rates data from API or None on failure
    """
    log_data = {
        'action': 'fetch_exchange_rates',
        'base_currency': base_currency.code,
        'target_count': len(target_currencies)
    }

    if not settings.EXCHANGE_RATES_KEY:
        log_data.update({
            'status': 'failed',
            'reason': 'api_key_not_configured'
        })
        logger.error(json.dumps(log_data))
        return None

    symbols = ','.join(target_currencies)

    params = {
        'access_key': settings.EXCHANGE_RATES_KEY,
        'base': base_currency.code,
        'symbols': symbols
    }

    try:
        log_data['url'] = settings.EXCHANGE_RATES_API_URL
        response = requests.get(
            settings.EXCHANGE_RATES_API_URL,
            params=params,
            timeout=10
        )

        log_data['status_code'] = response.status_code

        if response.status_code != 200:
            log_data.update({
                'status': 'failed',
                'reason': 'api_error',
                'response_body': response.text[:500]
            })
            logger.error(json.dumps(log_data))
            return None

        data = response.json()

        if not data.get('success', False):
            log_data.update({
                'status': 'failed',
                'reason': 'api_returned_error',
                'error': data.get('error', {})
            })
            logger.error(json.dumps(log_data))
            return None

        log_data.update({
            'status': 'success',
            'rates_count': len(data.get('rates', {}))
        })
        logger.info(json.dumps(log_data))

        return data

    except requests.exceptions.Timeout:
        log_data.update({
            'status': 'failed',
            'reason': 'timeout'
        })
        logger.error(json.dumps(log_data))
        return None

    except requests.exceptions.RequestException as e:
        log_data.update({
            'status': 'failed',
            'reason': 'request_exception',
            'error': str(e)
        })
        logger.error(json.dumps(log_data))
        return None

    except ValueError as e:
        log_data.update({
            'status': 'failed',
            'reason': 'json_decode_error',
            'error': str(e)
        })
        logger.error(json.dumps(log_data))
        return None


def update_rates_for_currency(base_currency, rates_data) -> None:
    """
    Update or create Rate objects from API response data.

    Args:
        base_currency: Currency object used as base
        rates_data: Rates dictionary from API response
    """
    log_data = {
        'action': 'update_rates',
        'base_currency': base_currency.code,
        'rates_updated': 0,
        'rates_created': 0
    }

    rates = rates_data.get('rates', {})

    for target_code, rate_value in rates.items():
        try:
            target_currency = Currency.objects.get(code=target_code)

            # Convert rate to Decimal
            mean_rate = Decimal(str(rate_value))

            # Calculate buying and selling rates with a small spread (e.g., 0.5%)
            spread = Decimal('0.005')
            buying_rate = mean_rate * (Decimal('1') - spread)
            selling_rate = mean_rate * (Decimal('1') + spread)

            rate_obj, created = Rate.objects.update_or_create(
                source=base_currency,
                target=target_currency,
                defaults={
                    'mean': mean_rate,
                    'buying': buying_rate,
                    'selling': selling_rate
                }
            )

            if created:
                log_data['rates_created'] += 1
            else:
                log_data['rates_updated'] += 1

        except Currency.DoesNotExist:
            continue
        except Exception as e:
            log_data.update({
                'target_currency': target_code,
                'error': str(e)
            })
            logger.warning(json.dumps(log_data))
            continue

    log_data['status'] = 'success'
    logger.info(json.dumps(log_data))


def update_all_exchange_rates() -> None:
    """
    Update exchange rates for all active currencies.
    This is the main function called by the Celery task.
    """
    log_data = {
        'action': 'update_all_exchange_rates',
        'timestamp': timezone.now().isoformat()
    }

    # Check if refresh is needed
    if not should_refresh_rates():
        log_data.update({
            'status': 'skipped',
            'reason': 'refresh_interval_not_reached'
        })
        logger.info(json.dumps(log_data))
        return

    # Get all active currencies
    active_currencies = list(Currency.objects.filter(active=True))

    if not active_currencies:
        log_data.update({
            'status': 'skipped',
            'reason': 'no_active_currencies'
        })
        logger.warning(json.dumps(log_data))
        return

    log_data['active_currencies_count'] = len(active_currencies)

    total_success = 0
    total_failed = 0

    # For each currency, fetch rates against all other active currencies
    for base_currency in active_currencies:
        # Get target currencies (all active except the base)
        target_codes = [c.code for c in active_currencies if c.code != base_currency.code]

        if not target_codes:
            continue

        # Fetch rates from API
        rates_data = fetch_rates_for_currency(base_currency, target_codes)

        if rates_data:
            update_rates_for_currency(base_currency, rates_data)
            total_success += 1
        else:
            total_failed += 1

    log_data.update({
        'status': 'completed',
        'successful_fetches': total_success,
        'failed_fetches': total_failed
    })
    logger.info(json.dumps(log_data))
