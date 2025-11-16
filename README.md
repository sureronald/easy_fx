# Easy FX - Currency Exchange API

A Django-based currency conversion API with automated exchange rate updates, quote generation, and expiration management.

## Setup and Running

### Prerequisites
- docker
- docker compose
- make

### Initial Setup

1. **Create environment file:**
   ```bash
   cp .env.example .env
   ```
   Update `.env` with your configuration, particularly:
   - `EXCHANGE_RATES_API_KEY` - Get a free API key from [exchangeratesapi.io](https://exchangeratesapi.io/)
   - `SECRET_KEY` - Generate a secure Django secret key
   - `DEBUG` - Set to `False` in production

2. **Complete setup (first time):**
   ```bash
   make setup
   ```
   This command will:
   - Build Docker images
   - Start all services (web, db, redis, celery worker, celery beat, nginx)
   - Run database migrations
   - Load initial fixtures (currencies and exchange rates)
   The app should be available on `http://localhost/fx`. Make sure port 80 is available.

3. **Access the application:**
   - API: http://localhost/fx/
   - Demo page: http://localhost/fx/demo/
   - Health check: http://localhost/fx/health/
   - Readiness check: http://localhost/fx/ready/

### Other Commands

View all available commands:
```bash
make help
```

Common commands:
- `make up` - Start services
- `make down` - Stop services
- `make logs` - View logs
- `make migrate` - Run database migrations
- `make loaddata` - Load fixtures
- `make test` - Run tests
- `make test-coverage` - Run tests with coverage report
- `make shell` - Access Django shell

### Running Tests

The test suite includes comprehensive unit tests with mocked external API calls:

```bash
# Run all tests
make test

# Run with coverage report
make test-coverage

# Run specific test module
docker compose exec web python manage.py test fx.tests.ExchangeRateServiceTest
```

Tests cover:
- Currency and Rate models
- Quote creation and validation
- API endpoints
- Exchange rate service with mocked API responses
- Form validation
- Error handling

## Design

### Architecture

Easy FX is a fully **Dockerized application** designed for portability and easy deployment. The multi-container setup includes:

- **Web Server (Django + Gunicorn)** - REST API and business logic
- **Database (PostgreSQL)** - Persistent data storage
- **Redis** - Message broker for Celery
- **Celery Worker** - Asynchronous task processing
- **Celery Beat** - Scheduled task management
- **Nginx** - Reverse proxy and static file serving

### Tech Stack

- **Backend Framework:** Django 4.2 + Django REST Framework
- **Database:** PostgreSQL 15
- **Task Queue:** Celery 5.3 with Redis broker
- **Web Server:** Gunicorn + Nginx
- **Monitoring:** Prometheus + Sentry
- **Testing:** pytest + pytest-django + pytest-cov

### Data Models

1. **Currency** - Stores currency metadata (code, name, symbol, formatting rules)
2. **Rate** - Exchange rates between currency pairs with mean/buying/selling rates
3. **Quote** - Time-limited conversion quotes with automatic expiration

### Rate Update Flow

1. Celery Beat triggers scheduled task based on `EXCHANGE_RATES_REFRESH` interval
2. Service checks rate staleness using `last_updated` timestamp
3. For each active currency as base, fetch rates from external API
4. Filter API response to only active currencies using `symbols` parameter
5. Update or create Rate entries with calculated buy/sell spread
6. All operations logged in JSON format for ELK stack compatibility

## Extras

### Rate Staleness Detection
The system implements intelligent rate refresh logic:
- Checks `last_updated` timestamp against `EXCHANGE_RATES_REFRESH` setting
- Skips unnecessary API calls if rates are still fresh
- Configurable refresh interval (default: 3000 seconds)

### Structured Logging
All operations are logged in JSON format for easy ingestion by ELK stack:
```json
{
  "action": "quote_create_request",
  "status": "success",
  "source_currency": "USD",
  "target_currency": "NGN",
  "amount": "100.00",
  "rate": "1443.100000"
}
```

### Monitoring
- **Prometheus** metrics via `django-prometheus` middleware
- **Sentry** error tracking and performance monitoring
- Metrics available at standard Prometheus endpoints

### Health Checks
- **`/fx/health/`** - Simple liveness check (returns 200 if service is running)
- **`/fx/ready/`** - Readiness check verifying:
  - Database connectivity
  - Exchange rates API accessibility
  - Returns detailed status for each dependency

### Management Commands
- `python manage.py update_exchange_rates` - Manually trigger rate updates
- `python manage.py loaddata fx/fixtures/currencies.json` - Load currencies
- `python manage.py loaddata fx/fixtures/rates.json` - Load initial rates

## Known Limitations

1. **Free API Tier Restrictions:**
   - Current API (exchangeratesapi.io) only supports EUR as base currency on free tier
   - Limited to 100 requests/month on free tier
   - Consider upgrading to paid tier or switching to alternative providers:
     - [Fixer.io](https://fixer.io/) - More generous free tier
     - [CurrencyAPI](https://currencyapi.com/) - Multiple base currencies on free tier
     - [Open Exchange Rates](https://openexchangerates.org/) - 1000 requests/month free

2. **No Request Caching:**
   - Redis infrastructure is in place but not utilized for caching API responses or caching the rates and currencies to reduce database queries
   - Potential optimization: Cache external API responses with TTL to reduce API calls
   - Implementation suggestion: Use `django-redis` for view-level caching

3. **Rate Coverage:**
   - Only 4 currencies (EUR, USD, NGN, KES) configured in fixtures
   - Can be extended by adding more currencies to fixtures or via admin panel

## Assumptions

- **Buy/Sell Spread:** A 0.5% spread is applied locally to generate buying and selling rates from the mean rate
  - `buying_rate = mean_rate * 0.995`
  - `selling_rate = mean_rate * 1.005`
- **Quote Validity:** Quotes expire after 60 seconds (configurable via `QUOTE_VALIDITY`)
- **Active Currencies:** Only currencies marked as `active=True` are included in rate updates
- **Rate Pairs:** Each currency pair is stored as a separate Rate entry (not bidirectional)
