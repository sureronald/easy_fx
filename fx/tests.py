from django.test import TestCase
from django.utils import timezone
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, Mock
from .models import Currency, Rate, Quote
from .forms import QuoteRequestForm
from .services import (
    should_refresh_rates,
    fetch_rates_for_currency,
    update_rates_for_currency,
    update_all_exchange_rates
)


class CurrencyModelTest(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            decimal_places=2,
            symbol_position='before'
        )

    def test_currency_creation(self):
        self.assertEqual(self.usd.code, 'USD')
        self.assertEqual(self.usd.name, 'US Dollar')
        self.assertTrue(self.usd.active)

    def test_currency_str(self):
        self.assertEqual(str(self.usd), 'USD - US Dollar')


class RateModelTest(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='US Dollar', symbol='$')
        self.kes = Currency.objects.create(code='KES', name='Kenyan Shilling', symbol='KSh')
        self.rate = Rate.objects.create(
            source=self.usd,
            target=self.kes,
            mean=Decimal('130.500000'),
            buying=Decimal('130.000000'),
            selling=Decimal('131.000000')
        )

    def test_rate_creation(self):
        self.assertEqual(self.rate.source.code, 'USD')
        self.assertEqual(self.rate.target.code, 'KES')
        self.assertEqual(self.rate.mean, Decimal('130.500000'))

    def test_rate_str(self):
        self.assertEqual(str(self.rate), 'USD/KES: 130.500000')

    def test_rate_unique_together(self):
        with self.assertRaises(Exception):
            Rate.objects.create(
                source=self.usd,
                target=self.kes,
                mean=Decimal('130.600000'),
                buying=Decimal('130.100000'),
                selling=Decimal('131.100000')
            )


class QuoteModelTest(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='US Dollar', symbol='$')
        self.ngn = Currency.objects.create(code='NGN', name='Nigerian Naira', symbol='₦')
        self.rate = Rate.objects.create(
            source=self.usd,
            target=self.ngn,
            mean=Decimal('1500.000000'),
            buying=Decimal('1495.000000'),
            selling=Decimal('1505.000000')
        )

    def test_quote_creation(self):
        quote = Quote.objects.create(
            source_currency=self.usd,
            target_currency=self.ngn,
            amount=Decimal('100.00'),
            rate=self.rate.mean,
            result=Decimal('150000.000000')
        )
        self.assertIsNotNone(quote.quote_id)
        self.assertIsNotNone(quote.expiration_time)
        self.assertEqual(quote.amount, Decimal('100.00'))

    def test_quote_expiration_time_set_on_save(self):
        quote = Quote.objects.create(
            source_currency=self.usd,
            target_currency=self.ngn,
            amount=Decimal('100.00'),
            rate=self.rate.mean,
            result=Decimal('150000.000000')
        )
        expected_expiration = timezone.now() + timedelta(seconds=getattr(settings, 'QUOTE_VALIDITY', 60))
        self.assertAlmostEqual(
            quote.expiration_time.timestamp(),
            expected_expiration.timestamp(),
            delta=2
        )

    def test_quote_is_expired_property(self):
        quote = Quote.objects.create(
            source_currency=self.usd,
            target_currency=self.ngn,
            amount=Decimal('100.00'),
            rate=self.rate.mean,
            result=Decimal('150000.000000')
        )
        self.assertFalse(quote.is_expired)

        quote.expiration_time = timezone.now() - timedelta(seconds=10)
        self.assertTrue(quote.is_expired)


class QuoteRequestFormTest(TestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='US Dollar', symbol='$', active=True)
        self.eur = Currency.objects.create(code='EUR', name='Euro', symbol='€', active=True)
        self.kes = Currency.objects.create(code='KES', name='Kenyan Shilling', symbol='KSh', active=False)
        self.rate = Rate.objects.create(
            source=self.usd,
            target=self.eur,
            mean=Decimal('0.920000'),
            buying=Decimal('0.915000'),
            selling=Decimal('0.925000')
        )

    def test_valid_form(self):
        form = QuoteRequestForm(data={
            'source_currency': 'USD',
            'target_currency': 'EUR',
            'amount': '100.00'
        })
        self.assertTrue(form.is_valid())

    def test_invalid_source_currency(self):
        form = QuoteRequestForm(data={
            'source_currency': 'XXX',
            'target_currency': 'EUR',
            'amount': '100.00'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('source_currency', form.errors)

    def test_inactive_currency(self):
        form = QuoteRequestForm(data={
            'source_currency': 'KES',
            'target_currency': 'EUR',
            'amount': '100.00'
        })
        self.assertFalse(form.is_valid())

    def test_same_source_and_target(self):
        form = QuoteRequestForm(data={
            'source_currency': 'USD',
            'target_currency': 'USD',
            'amount': '100.00'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_no_rate_available(self):
        form = QuoteRequestForm(data={
            'source_currency': 'EUR',
            'target_currency': 'USD',
            'amount': '100.00'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_invalid_amount(self):
        form = QuoteRequestForm(data={
            'source_currency': 'USD',
            'target_currency': 'EUR',
            'amount': '-100.00'
        })
        self.assertFalse(form.is_valid())


class QuoteViewSetTest(APITestCase):
    def setUp(self):
        self.usd = Currency.objects.create(code='USD', name='US Dollar', symbol='$', active=True)
        self.kes = Currency.objects.create(code='KES', name='Kenyan Shilling', symbol='KSh', active=True)
        self.ngn = Currency.objects.create(code='NGN', name='Nigerian Naira', symbol='₦', active=True)
        self.eur = Currency.objects.create(code='EUR', name='Euro', symbol='€', active=True)

        Rate.objects.create(
            source=self.usd,
            target=self.kes,
            mean=Decimal('130.500000'),
            buying=Decimal('130.000000'),
            selling=Decimal('131.000000')
        )
        Rate.objects.create(
            source=self.usd,
            target=self.ngn,
            mean=Decimal('1500.000000'),
            buying=Decimal('1495.000000'),
            selling=Decimal('1505.000000')
        )
        Rate.objects.create(
            source=self.eur,
            target=self.usd,
            mean=Decimal('1.080000'),
            buying=Decimal('1.075000'),
            selling=Decimal('1.085000')
        )

    def test_create_quote_success(self):
        data = {
            'source_currency': 'USD',
            'target_currency': 'KES',
            'amount': '100.00'
        }
        response = self.client.post('/fx/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('quote_id', response.data)
        self.assertIn('rate', response.data)
        self.assertIn('result', response.data)
        self.assertEqual(response.data['amount'], '100.00')

    def test_create_quote_invalid_currency(self):
        data = {
            'source_currency': 'XXX',
            'target_currency': 'KES',
            'amount': '100.00'
        }
        response = self.client.post('/fx/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_quote_missing_fields(self):
        data = {
            'source_currency': 'USD',
            'amount': '100.00'
        }
        response = self.client.post('/fx/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_quote_same_currencies(self):
        data = {
            'source_currency': 'USD',
            'target_currency': 'USD',
            'amount': '100.00'
        }
        response = self.client.post('/fx/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_quote_success(self):
        quote = Quote.objects.create(
            source_currency=self.usd,
            target_currency=self.ngn,
            amount=Decimal('200.00'),
            rate=Decimal('1500.000000'),
            result=Decimal('300000.000000')
        )
        response = self.client.get(f'/fx/{quote.quote_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(response.data['quote_id']), str(quote.quote_id))

    def test_retrieve_expired_quote(self):
        quote = Quote.objects.create(
            source_currency=self.usd,
            target_currency=self.ngn,
            amount=Decimal('200.00'),
            rate=Decimal('1500.000000'),
            result=Decimal('300000.000000')
        )
        quote.expiration_time = timezone.now() - timedelta(seconds=10)
        quote.save()

        response = self.client.get(f'/fx/{quote.quote_id}/')
        self.assertEqual(response.status_code, status.HTTP_410_GONE)

    def test_retrieve_nonexistent_quote(self):
        response = self.client.get('/fx/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ExchangeRateServiceTest(TestCase):
    def setUp(self):
        self.eur = Currency.objects.create(code='EUR', name='Euro', symbol='€', active=True)
        self.usd = Currency.objects.create(code='USD', name='US Dollar', symbol='$', active=True)
        self.ngn = Currency.objects.create(code='NGN', name='Nigerian Naira', symbol='₦', active=True)
        self.kes = Currency.objects.create(code='KES', name='Kenyan Shilling', symbol='KSh', active=True)

    def test_should_refresh_rates_no_existing_rates(self):
        """Test that refresh is needed when no rates exist"""
        result = should_refresh_rates()
        self.assertTrue(result)

    def test_should_refresh_rates_recent_update(self):
        """Test that refresh is not needed when rates are recent"""
        Rate.objects.create(
            source=self.eur,
            target=self.usd,
            mean=Decimal('1.163725'),
            buying=Decimal('1.157906'),
            selling=Decimal('1.169544')
        )
        result = should_refresh_rates()
        self.assertFalse(result)

    def test_should_refresh_rates_stale_update(self):
        """Test that refresh is needed when rates are stale"""
        rate = Rate.objects.create(
            source=self.eur,
            target=self.usd,
            mean=Decimal('1.163725'),
            buying=Decimal('1.157906'),
            selling=Decimal('1.169544')
        )
        # Manually set last_updated to past the refresh interval
        stale_time = timezone.now() - timedelta(seconds=settings.EXCHANGE_RATES_REFRESH + 100)
        Rate.objects.filter(pk=rate.pk).update(last_updated=stale_time)

        result = should_refresh_rates()
        self.assertTrue(result)

    @patch('fx.services.requests.get')
    def test_fetch_rates_for_currency_success(self, mock_get):
        """Test successful API call to fetch exchange rates"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "timestamp": 1763105647,
            "base": "EUR",
            "date": "2025-11-14",
            "rates": {
                "NGN": 1679.196164,
                "KES": 150.411993,
                "USD": 1.163725
            }
        }
        mock_get.return_value = mock_response

        result = fetch_rates_for_currency(self.eur, ['NGN', 'KES', 'USD'])

        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(result['base'], 'EUR')
        self.assertIn('NGN', result['rates'])
        self.assertIn('KES', result['rates'])
        self.assertIn('USD', result['rates'])

        # Verify the API was called correctly
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]['params']['base'], 'EUR')
        self.assertEqual(call_args[1]['params']['symbols'], 'NGN,KES,USD')
        self.assertIn('access_key', call_args[1]['params'])

    @patch('fx.services.requests.get')
    def test_fetch_rates_for_currency_api_error(self, mock_get):
        """Test handling of API error response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        mock_get.return_value = mock_response

        result = fetch_rates_for_currency(self.eur, ['NGN', 'KES', 'USD'])

        self.assertIsNone(result)

    @patch('fx.services.requests.get')
    def test_fetch_rates_for_currency_api_returns_error(self, mock_get):
        """Test handling when API returns success=false"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": False,
            "error": {
                "code": 101,
                "type": "invalid_access_key"
            }
        }
        mock_get.return_value = mock_response

        result = fetch_rates_for_currency(self.eur, ['NGN', 'KES', 'USD'])

        self.assertIsNone(result)

    @patch('fx.services.requests.get')
    def test_fetch_rates_for_currency_timeout(self, mock_get):
        """Test handling of request timeout"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout()

        result = fetch_rates_for_currency(self.eur, ['NGN', 'KES', 'USD'])

        self.assertIsNone(result)

    @patch('fx.services.requests.get')
    def test_fetch_rates_for_currency_request_exception(self, mock_get):
        """Test handling of general request exception"""
        import requests
        mock_get.side_effect = requests.exceptions.RequestException('Connection error')

        result = fetch_rates_for_currency(self.eur, ['NGN', 'KES', 'USD'])

        self.assertIsNone(result)

    @patch('fx.services.settings.EXCHANGE_RATES_KEY', '')
    def test_fetch_rates_for_currency_no_api_key(self):
        """Test that fetch fails gracefully when API key is not configured"""
        result = fetch_rates_for_currency(self.eur, ['NGN', 'KES', 'USD'])

        self.assertIsNone(result)

    def test_update_rates_for_currency(self):
        """Test updating rates from API response data"""
        api_response = {
            "success": True,
            "timestamp": 1763105647,
            "base": "EUR",
            "date": "2025-11-14",
            "rates": {
                "NGN": 1679.196164,
                "KES": 150.411993,
                "USD": 1.163725
            }
        }

        update_rates_for_currency(self.eur, api_response)

        # Check that rates were created
        self.assertEqual(Rate.objects.count(), 3)

        # Check EUR to NGN rate
        ngn_rate = Rate.objects.get(source=self.eur, target=self.ngn)
        self.assertEqual(ngn_rate.mean, Decimal('1679.196164'))
        self.assertLess(ngn_rate.buying, ngn_rate.mean)
        self.assertGreater(ngn_rate.selling, ngn_rate.mean)

        # Check EUR to KES rate
        kes_rate = Rate.objects.get(source=self.eur, target=self.kes)
        self.assertEqual(kes_rate.mean, Decimal('150.411993'))

        # Check EUR to USD rate
        usd_rate = Rate.objects.get(source=self.eur, target=self.usd)
        self.assertEqual(usd_rate.mean, Decimal('1.163725'))

    def test_update_rates_for_currency_updates_existing(self):
        """Test that existing rates are updated rather than duplicated"""
        # Create an existing rate
        Rate.objects.create(
            source=self.eur,
            target=self.usd,
            mean=Decimal('1.100000'),
            buying=Decimal('1.095000'),
            selling=Decimal('1.105000')
        )

        api_response = {
            "success": True,
            "rates": {
                "USD": 1.163725
            }
        }

        update_rates_for_currency(self.eur, api_response)

        # Check that only one rate exists and it was updated
        self.assertEqual(Rate.objects.count(), 1)
        usd_rate = Rate.objects.get(source=self.eur, target=self.usd)
        self.assertEqual(usd_rate.mean, Decimal('1.163725'))

    @patch('fx.services.fetch_rates_for_currency')
    def test_update_all_exchange_rates_success(self, mock_fetch):
        """Test full update process for all currencies"""
        mock_fetch.return_value = {
            "success": True,
            "rates": {
                "NGN": 1679.196164,
                "KES": 150.411993,
                "USD": 1.163725
            }
        }

        update_all_exchange_rates()

        # Each currency should be used as base (4 currencies)
        self.assertEqual(mock_fetch.call_count, 4)

        # Check that rates were created
        self.assertGreater(Rate.objects.count(), 0)

    @patch('fx.services.fetch_rates_for_currency')
    def test_update_all_exchange_rates_skips_when_not_needed(self, mock_fetch):
        """Test that update is skipped when refresh interval hasn't elapsed"""
        # Create a recent rate
        Rate.objects.create(
            source=self.eur,
            target=self.usd,
            mean=Decimal('1.163725'),
            buying=Decimal('1.157906'),
            selling=Decimal('1.169544')
        )

        update_all_exchange_rates()

        # Should not have called the API
        mock_fetch.assert_not_called()

    def test_update_all_exchange_rates_no_active_currencies(self):
        """Test handling when no active currencies exist"""
        Currency.objects.all().update(active=False)

        # Should not raise an error
        update_all_exchange_rates()

    @patch('fx.services.fetch_rates_for_currency')
    def test_update_all_exchange_rates_handles_api_failure(self, mock_fetch):
        """Test that process continues even if some API calls fail"""
        # First call succeeds, others fail
        mock_fetch.side_effect = [
            {
                "success": True,
                "rates": {
                    "NGN": 1679.196164,
                    "KES": 150.411993,
                    "USD": 1.163725
                }
            },
            None,  # API failure
            None,  # API failure
            None   # API failure
        ]

        update_all_exchange_rates()

        # Should have attempted to fetch for all currencies
        self.assertEqual(mock_fetch.call_count, 4)

        # Should have created rates from the successful call
        self.assertGreater(Rate.objects.count(), 0)
