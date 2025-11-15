import logging
import json
import requests
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import connection
from .models import Quote, Rate
from .serializers import QuoteSerializer
from .forms import QuoteRequestForm

logger = logging.getLogger('fx')


class QuoteViewSet(viewsets.ViewSet):
    def create(self, request):
        log_data = {
            'action': 'quote_create_request',
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT'),
        }

        form = QuoteRequestForm(data=request.data)

        if not form.is_valid():
            log_data.update({
                'status': 'failed',
                'reason': 'validation_error',
                'errors': str(form.errors)
            })
            logger.warning(json.dumps(log_data))
            return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)

        source_currency = form.cleaned_data['source_currency']
        target_currency = form.cleaned_data['target_currency']
        amount = form.cleaned_data['amount']

        log_data.update({
            'source_currency': source_currency.code,
            'target_currency': target_currency.code,
            'amount': str(amount)
        })

        rate_obj = Rate.objects.get(source=source_currency, target=target_currency)
        result = amount * rate_obj.mean

        quote = Quote.objects.create(
            source_currency=source_currency,
            target_currency=target_currency,
            amount=amount,
            rate=rate_obj.mean,
            result=result
        )

        log_data.update({
            'status': 'success',
            'quote_id': str(quote.quote_id),
            'rate': str(rate_obj.mean),
            'result': str(result)
        })
        logger.info(json.dumps(log_data))

        serializer = QuoteSerializer(quote)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        log_data = {
            'action': 'quote_retrieve_request',
            'quote_id': str(pk),
            'ip_address': request.META.get('REMOTE_ADDR'),
        }

        quote = get_object_or_404(Quote, pk=pk)

        if quote.is_expired:
            log_data.update({
                'status': 'failed',
                'reason': 'quote_expired',
                'expiration_time': quote.expiration_time.isoformat()
            })
            logger.warning(json.dumps(log_data))
            return Response(
                {'error': 'Quote has expired'},
                status=status.HTTP_410_GONE
            )

        log_data.update({
            'status': 'success',
            'source_currency': quote.source_currency.code,
            'target_currency': quote.target_currency.code,
            'amount': str(quote.amount)
        })
        logger.info(json.dumps(log_data))

        serializer = QuoteSerializer(quote)
        return Response(serializer.data)


@api_view(['GET'])
def health_check(request):
    """
    Simple health check endpoint that returns 200 if service is running.
    """
    log_data = {
        'action': 'health_check',
        'status': 'healthy'
    }
    logger.info(json.dumps(log_data))
    return Response({'status': 'healthy'}, status=status.HTTP_200_OK)


@api_view(['GET'])
def readiness_check(request):
    """
    Readiness check endpoint that verifies:
    - Database connectivity
    - Exchange rates API accessibility
    """
    log_data = {
        'action': 'readiness_check',
        'checks': {}
    }

    checks_passed = True

    # Check database connectivity
    try:
        connection.ensure_connection()
        log_data['checks']['database'] = 'ok'
    except Exception as e:
        log_data['checks']['database'] = 'failed'
        log_data['database_error'] = str(e)
        checks_passed = False

    # Check exchange rates API
    if settings.EXCHANGE_RATES_KEY:
        try:
            response = requests.get(
                settings.EXCHANGE_RATES_API_URL,
                params={'access_key': settings.EXCHANGE_RATES_KEY},
                timeout=5
            )
            if response.status_code == 200:
                log_data['checks']['exchange_rates_api'] = 'ok'
            else:
                log_data['checks']['exchange_rates_api'] = 'failed'
                log_data['api_status_code'] = response.status_code
                checks_passed = False
        except requests.exceptions.Timeout:
            log_data['checks']['exchange_rates_api'] = 'timeout'
            checks_passed = False
        except Exception as e:
            log_data['checks']['exchange_rates_api'] = 'failed'
            log_data['api_error'] = str(e)
            checks_passed = False
    else:
        log_data['checks']['exchange_rates_api'] = 'no_api_key'
        checks_passed = False

    if checks_passed:
        log_data['status'] = 'ready'
        logger.info(json.dumps(log_data))
        return Response(log_data, status=status.HTTP_200_OK)
    else:
        log_data['status'] = 'not_ready'
        logger.warning(json.dumps(log_data))
        return Response(log_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)


def demo_page(request):
    """
    Demo page for currency conversion.
    """
    from django.shortcuts import render
    from .models import Currency

    # Get all active currencies
    currencies = Currency.objects.filter(active=True).order_by('code')

    return render(request, 'fx/demo.html', {'currencies': currencies})
