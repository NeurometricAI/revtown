.PHONY: help dev dev-api dev-web stop clean test lint format typecheck install db-init db-migrate logs shell

# Default target
help:
	@echo "RevTown Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev          - Start all services (Dolt, Kafka, Temporal, Vault, API, Web)"
	@echo "  make dev-api      - Start backend services only"
	@echo "  make dev-web      - Start frontend dev server (requires API running)"
	@echo "  make stop         - Stop all services"
	@echo "  make clean        - Stop services and remove volumes"
	@echo ""
	@echo "Testing:"
	@echo "  make test         - Run all tests"
	@echo "  make test-unit    - Run unit tests only"
	@echo "  make test-int     - Run integration tests only"
	@echo "  make test-e2e     - Run end-to-end tests"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint         - Run linters (ruff, eslint)"
	@echo "  make format       - Format code (ruff, prettier)"
	@echo "  make typecheck    - Run type checkers (mypy, tsc)"
	@echo ""
	@echo "Setup:"
	@echo "  make install      - Install all dependencies"
	@echo "  make db-init      - Initialize Dolt database with schema"
	@echo "  make db-migrate   - Run database migrations"
	@echo ""
	@echo "Utilities:"
	@echo "  make logs         - Tail logs from all services"
	@echo "  make logs-api     - Tail API logs"
	@echo "  make shell-api    - Open shell in API container"
	@echo "  make shell-dolt   - Open Dolt SQL shell"

# =============================================================================
# Development
# =============================================================================

dev:
	docker-compose up -d

dev-api:
	docker-compose up -d dolt redpanda temporal temporal-db temporal-ui vault api

dev-web:
	cd apps/web && npm run dev

stop:
	docker-compose stop

clean:
	docker-compose down -v
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# Testing
# =============================================================================

test:
	poetry run pytest

test-unit:
	poetry run pytest tests/unit -v

test-int:
	poetry run pytest tests/integration -v

test-e2e:
	poetry run pytest tests/e2e -v

test-cov:
	poetry run pytest --cov=apps --cov=polecats --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# =============================================================================
# Code Quality
# =============================================================================

lint:
	poetry run ruff check .
	cd apps/web && npm run lint

format:
	poetry run ruff format .
	poetry run ruff check --fix .
	cd apps/web && npm run format

typecheck:
	poetry run mypy apps polecats plugins rigs
	cd apps/web && npm run typecheck

# =============================================================================
# Setup
# =============================================================================

install:
	poetry install
	cd apps/web && npm install

db-init:
	@echo "Initializing Dolt database..."
	docker-compose exec dolt dolt sql -q "CREATE DATABASE IF NOT EXISTS revtown"
	docker-compose exec dolt dolt sql -u root -d revtown < db/schema/init.sql
	@echo "Database initialized."

db-migrate:
	@echo "Running migrations..."
	docker-compose exec dolt dolt sql -u root -d revtown < db/schema/migrations/latest.sql
	docker-compose exec dolt dolt add .
	docker-compose exec dolt dolt commit -m "Migration: $$(date +%Y%m%d%H%M%S)"
	@echo "Migration complete."

# =============================================================================
# Utilities
# =============================================================================

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

shell-api:
	docker-compose exec api /bin/bash

shell-dolt:
	docker-compose exec dolt dolt sql -u root -d revtown

# =============================================================================
# Production Builds
# =============================================================================

build:
	docker build -t revtown-api:latest .
	cd apps/web && npm run build

build-api:
	docker build -t revtown-api:latest .

build-web:
	cd apps/web && npm run build
