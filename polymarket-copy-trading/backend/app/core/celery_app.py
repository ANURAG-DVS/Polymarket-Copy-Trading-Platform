"""
Celery application configuration and initialization.

This module sets up the Celery app for background task processing,
including beat schedule for periodic tasks.
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "polymarket_copy_trading",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    #Fetch top traders every 5 minutes
    'fetch-top-traders-every-5-minutes': {
        'task': 'fetch_top_traders_task',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'args': (100, 7),  # limit=100, timeframe_days=7
        'options': {
            'expires': 240,  # Task expires after 4 minutes
        }
    },
    
    # Calculate leaderboard every minute
    'calculate-leaderboard-every-minute': {
        'task': 'calculate_leaderboard_task',
        'schedule': crontab(minute='*'),  # Every minute
        'options': {
            'expires': 50,  # Task expires after 50 seconds
        }
    },
    
    # Sync trader positions every 10 minutes
    'sync-trader-positions-every-10-minutes': {
        'task': 'sync_trader_positions_task',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'kwargs': {'limit': 50},  # Top 50 traders
        'options': {
            'expires': 540,  # Task expires after 9 minutes
        }
    },
}

# Auto-discover tasks from all registered Django apps
celery_app.autodiscover_tasks(['app.workers'])
