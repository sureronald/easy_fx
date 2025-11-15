.PHONY: build up down restart logs shell migrate makemigrations test createsuperuser clean ps loaddata setup

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

shell:
	docker compose exec web python manage.py shell

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

test:
	docker compose exec web python manage.py test

test-coverage:
	docker compose exec web pytest --cov=fx --cov-report=html --cov-report=term

createsuperuser:
	docker compose exec web python manage.py createsuperuser

collectstatic:
	docker compose exec web python manage.py collectstatic --noinput

loaddata:
	docker compose exec web python manage.py loaddata fx/fixtures/currencies.json
	docker compose exec web python manage.py loaddata fx/fixtures/rates.json

setup: build up migrate loaddata
	@echo "Setup complete! Services are running."

ps:
	docker compose ps

clean:
	docker compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

dev-up:
	docker compose up

prod-build:
	docker build -t easy_fx:latest .

help:
	@echo "Available commands:"
	@echo "  make build           - Build Docker images"
	@echo "  make up              - Start services in detached mode"
	@echo "  make down            - Stop services"
	@echo "  make restart         - Restart services"
	@echo "  make logs            - View logs"
	@echo "  make shell           - Access Django shell"
	@echo "  make migrate         - Run migrations"
	@echo "  make makemigrations  - Create migrations"
	@echo "  make test            - Run tests"
	@echo "  make test-coverage   - Run tests with coverage"
	@echo "  make createsuperuser - Create superuser"
	@echo "  make collectstatic   - Collect static files"
	@echo "  make loaddata        - Load all fixtures"
	@echo "  make setup           - Complete setup (build, up, migrate, loaddata)"
	@echo "  make ps              - Show running containers"
	@echo "  make clean           - Clean up containers and volumes"
	@echo "  make dev-up          - Start services in foreground"
	@echo "  make prod-build      - Build production Docker image"
