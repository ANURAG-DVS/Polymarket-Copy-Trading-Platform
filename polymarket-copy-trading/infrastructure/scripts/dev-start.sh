#!/bin/bash
set -e

echo "🚀 Starting development environment..."

# Check if .env files exist
if [ ! -f "backend/.env" ]; then
    echo "⚠️  backend/.env not found. Copying from .env.example..."
    cp backend/.env.example backend/.env
fi

if [ ! -f "frontend/.env" ]; then
    echo "⚠️  frontend/.env not found. Copying from .env.example..."
    cp frontend/.env.example frontend/.env
fi

if [ ! -f "telegram-bot/.env" ]; then
    echo "⚠️  telegram-bot/.env not found. Copying from .env.example..."
    cp telegram-bot/.env.example telegram-bot/.env
fi

# Start Docker Compose
echo "🐳 Starting Docker containers..."
docker-compose up -d

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Run database migrations
echo "📊 Running database migrations..."
docker-compose exec -T backend alembic upgrade head || echo "⚠️  Migrations not ready yet. Run manually: docker-compose exec backend alembic upgrade head"

echo "✅ Development environment started!"
echo ""
echo "📍 Services:"
echo "   - Backend API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Frontend: http://localhost:3000"
echo "   - Flower (Celery): http://localhost:5555"
echo ""
echo "📝 View logs: docker-compose logs -f"
echo "🛑 Stop services: docker-compose down"
