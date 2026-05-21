# Atlas AI Coding Agent - Makefile
# Usage: make <command>

.PHONY: help install dev build up down logs clean test lint format

# Default target
help:
	@echo "Atlas AI Coding Agent - Available Commands:"
	@echo ""
	@echo "  make install       Install all dependencies (frontend + backend)"
	@echo "  make dev           Start development servers (frontend + backend + infra)"
	@echo "  make dev-frontend  Start frontend dev server only"
	@echo "  make dev-backend   Start backend dev server only"
	@echo "  make build         Build production Docker images"
	@echo "  make up            Start all services with Docker Compose"
	@echo "  make down          Stop all services"
	@echo "  make logs          View logs from all services"
	@echo "  make logs-backend  View backend logs only"
	@echo "  make logs-frontend View frontend logs only"
	@echo "  make clean         Remove all containers, volumes, and temp files"
	@echo "  make test          Run all tests"
	@echo "  make test-backend  Run backend tests only"
	@echo "  make test-frontend Run frontend tests only"
	@echo "  make lint          Run linters on both frontend and backend"
	@echo "  make format        Format code with black (backend) and prettier (frontend)"
	@echo "  make migrate       Run database migrations"
	@echo "  make seed          Seed database with sample data"
	@echo "  make shell-backend Open a shell in the backend container"
	@echo "  make shell-db      Open PostgreSQL shell"
	@echo "  make redis-cli     Open Redis CLI"
	@echo ""

# ==================== INSTALL ====================

install: install-backend install-frontend
	@echo "✅ All dependencies installed"

install-backend:
	cd backend && python -m venv venv
	cd backend && . venv/bin/activate && pip install -r requirements.txt
	@echo "✅ Backend dependencies installed"

install-frontend:
	cd frontend && npm install
	@echo "✅ Frontend dependencies installed"

# ==================== DEVELOPMENT ====================

dev:
	docker-compose -f docker-compose.dev.yml up --build

dev-frontend:
	cd frontend && npm run dev

dev-backend:
	cd backend && . venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ==================== DOCKER ====================

build:
	docker-compose build --no-cache

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

logs-backend:
	docker-compose logs -f backend

logs-frontend:
	docker-compose logs -f frontend

# ==================== CLEANUP ====================

clean:
	docker-compose down -v --remove-orphans
	docker system prune -f
	rm -rf frontend/node_modules frontend/.next
	rm -rf backend/venv backend/__pycache__ backend/**/__pycache__
	rm -rf /tmp/repos/*
	@echo "🧹 Cleanup complete"

# ==================== TESTING ====================

test: test-backend test-frontend
	@echo "✅ All tests passed"

test-backend:
	cd backend && . venv/bin/activate && pytest -v

test-frontend:
	cd frontend && npm test

# ==================== LINT & FORMAT ====================

lint: lint-backend lint-frontend
	@echo "✅ Linting complete"

lint-backend:
	cd backend && . venv/bin/activate && flake8 app/ --max-line-length=100
	cd backend && . venv/bin/activate && mypy app/

lint-frontend:
	cd frontend && npm run lint

format:
	cd backend && . venv/bin/activate && black app/ --line-length=100
	cd backend && . venv/bin/activate && isort app/
	cd frontend && npx prettier --write "**/*.{ts,tsx,js,jsx,json,css,md}"
	@echo "✅ Code formatted"

# ==================== DATABASE ====================

migrate:
	cd backend && . venv/bin/activate && alembic upgrade head

migrate-make:
	@read -p "Migration message: " msg; \
	cd backend && . venv/bin/activate && alembic revision --autogenerate -m "$$msg"

seed:
	cd backend && . venv/bin/activate && python scripts/seed.py

# ==================== SHELL ACCESS ====================

shell-backend:
	docker-compose exec backend /bin/bash

shell-db:
	docker-compose exec postgres psql -U atlas -d atlas

redis-cli:
	docker-compose exec redis redis-cli

# ==================== DEPLOYMENT ====================

deploy-staging:
	docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d --build

deploy-prod:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# ==================== AI API CHECK ====================

check-apis:
	@echo "Checking AI API keys..."
	@python3 -c "import os; \
	keys = ['GEMINI_API_KEY', 'GROQ_API_KEY', 'OPENROUTER_API_KEY']; \
	[print(f'  {k}: {\"✅ SET\" if os.getenv(k) else \"❌ MISSING\"}') for k in keys]"

# ==================== REPO MANAGEMENT ====================

index-repo:
	@read -p "GitHub repo URL: " url; \
	curl -X POST http://localhost:8000/api/repos/ \
	  -H "Content-Type: application/json" \
	  -d "{\"url\": \"$$url\"}"

# ==================== SHORTCUTS ====================

# Quick start everything
start: up logs

# Full reset and restart
restart: clean up logs
