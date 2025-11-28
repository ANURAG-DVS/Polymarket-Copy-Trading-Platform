"""Celery application configuration"""

from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "polymarket_copy_trading",
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND),
)

# Configure Celery
celery_app.conf.update(
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'app.workers.blockchain.*': {'queue': 'blockchain'},
        'app.workers.trades.*': {'queue': 'trades'},
        'app.workers.notifications.*': {'queue': 'notifications'},
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['app.workers'])


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing"""
    print(f'Request: {self.request!r}')
