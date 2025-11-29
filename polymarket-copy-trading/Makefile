.PHONY: help dev prod build test clean logs shell migrate

# Variables
COMPOSE_DEV = docker-compose -f docker-compose.dev.yml
COMPOSE_PROD = docker-compose -f docker-compose.prod.yml

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Development
dev: ## Start development environment
	@echo "🚀 Starting development environment..."
	$(COMPOSE_DEV) up -d
	@echo "✅ Development environment started!"
	@echo "   Backend API: http://localhost:8000"
	@echo "   API Docs: http://localhost:8000/docs"
	@echo "   PGAdmin: http://localhost:5050"
	@echo "   MailHog: http://localhost:8025"
	@echo "   Redis Commander: http://localhost:8081"

dev-build: ## Build and start development environment
	@echo "🔨 Building development environment..."
	$(COMPOSE_DEV) up -d --build

dev-stop: ## Stop development environment
	@echo "🛑 Stopping development environment..."
	$(COMPOSE_DEV) down

dev-restart: ## Restart development environment
	@echo "🔄 Restarting development environment..."
	$(COMPOSE_DEV) restart

# Production
prod: ## Start production environment
	@echo "🚀 Starting production environment..."
	$(COMPOSE_PROD) up -d
	@echo "✅ Production environment started!"

prod-build: ## Build and start production environment
	@echo "🔨 Building production environment..."
	$(COMPOSE_PROD) up -d --build

prod-stop: ## Stop production environment
	@echo "🛑 Stopping production environment..."
	$(COMPOSE_PROD) down

prod-scale: ## Scale production workers
	@echo "📈 Scaling production workers..."
	$(COMPOSE_PROD) up -d --scale celery_worker=5

# Build
build: ## Build all Docker images
	@echo "🔨 Building all Docker images..."
	docker build -t polymarket-backend:latest ./backend
	docker build -t polymarket-worker:latest -f ./backend/Dockerfile.worker ./backend
	docker build -t polymarket-beat:latest -f ./backend/Dockerfile.beat ./backend
	docker build -t polymarket-telegram:latest ./telegram-bot
	@echo "✅ All images built!"

build-backend: ## Build backend image
	@echo "🔨 Building backend image..."
	docker build -t polymarket-backend:latest ./backend

build-worker: ## Build worker image
	@echo "🔨 Building worker image..."
	docker build -t polymarket-worker:latest -f ./backend/Dockerfile.worker ./backend

build-telegram: ## Build telegram bot image
	@echo "🔨 Building telegram bot image..."
	docker build -t polymarket-telegram:latest ./telegram-bot

# Testing
test: ## Run tests
	@echo "🧪 Running tests..."
	$(COMPOSE_DEV) exec backend pytest tests/ -v

test-cov: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	$(COMPOSE_DEV) exec backend pytest tests/ -v --cov=app --cov-report=html

# Database
migrate: ## Run database migrations
	@echo "🗄️  Running database migrations..."
	$(COMPOSE_DEV) exec backend alembic upgrade head

migrate-create: ## Create new migration
	@read -p "Enter migration message: " msg; \
	$(COMPOSE_DEV) exec backend alembic revision --autogenerate -m "$$msg"

db-shell: ## Open database shell
	@echo "🗄️  Opening database shell..."
	$(COMPOSE_DEV) exec postgres psql -U postgres -d polymarket_copy_dev

# Logs
logs: ## View logs for all services
	$(COMPOSE_DEV) logs -f

logs-backend: ## View backend logs
	$(COMPOSE_DEV) logs -f backend

logs-worker: ## View worker logs
	$(COMPOSE_DEV) logs -f celery_worker

logs-telegram: ## View telegram bot logs
	$(COMPOSE_DEV) logs -f telegram_bot

# Shell Access
shell-backend: ## Shell into backend container
	$(COMPOSE_DEV) exec backend /bin/bash

shell-worker: ## Shell into worker container
	$(COMPOSE_DEV) exec celery_worker /bin/bash

shell-postgres: ## Shell into postgres container
	$(COMPOSE_DEV) exec postgres /bin/bash

# Cleanup
clean: ## Remove all containers, volumes, and images
	@echo "🧹 Cleaning up..."
	$(COMPOSE_DEV) down -v
	docker system prune -af
	@echo "✅ Cleanup complete!"

clean-volumes: ## Remove all volumes
	@echo "🧹 Removing volumes..."
	$(COMPOSE_DEV) down -v

# Validation
validate-env: ## Validate environment configuration
	@echo "🔍 Validating environment configuration..."
	python scripts/validate_env.py --env-file .env.development

validate-docker: ## Validate Docker configuration
	@echo "🔍 Validating Docker configuration..."
	docker-compose -f docker-compose.dev.yml config
	docker-compose -f docker-compose.prod.yml config

# Security
scan: ## Scan images for vulnerabilities
	@echo "🔒 Scanning images for vulnerabilities..."
	trivy image polymarket-backend:latest
	trivy image polymarket-worker:latest
	trivy image polymarket-telegram:latest

# Monitoring
stats: ## Show container stats
	docker stats

ps: ## Show running containers
	$(COMPOSE_DEV) ps

# Quick Commands
up: dev ## Alias for 'make dev'
down: dev-stop ## Alias for 'make dev-stop'
restart: dev-restart ## Alias for 'make dev-restart'
