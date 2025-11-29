from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings
import httpx
import time
import psutil
from datetime import datetime

router = APIRouter()

start_time = time.time()

@router.get("/health")
async def health_check():
    """Basic health check - service is up"""
    return {
        "status": "healthy",
        "service": "polymarket-copy-trading",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check - all dependencies"""
    
    health_status = {
        "status": "healthy",
        "service": "polymarket-copy-trading",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int(time.time() - start_time),
        "checks": {}
    }
    
    all_healthy = True
    
    # Database check
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()
        health_status["checks"]["database"] = {
            "status": "healthy",
            "latency_ms": 0  # Could measure actual latency
        }
    except Exception as e:
        all_healthy = False
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Redis check
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        health_status["checks"]["redis"] = {
            "status": "healthy"
        }
    except Exception as e:
        all_healthy = False
        health_status["checks"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Polymarket API check
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.POLYMARKET_API_BASE_URL}/markets")
            if response.status_code == 200:
                health_status["checks"]["polymarket_api"] = {
                    "status": "healthy",
                    "latency_ms": int(response.elapsed.total_seconds() * 1000)
                }
            else:
                all_healthy = False
                health_status["checks"]["polymarket_api"] = {
                    "status": "degraded",
                    "status_code": response.status_code
                }
    except Exception as e:
        all_healthy = False
        health_status["checks"]["polymarket_api"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # System metrics
    health_status["system"] = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent
    }
    
    # Overall status
    if not all_healthy:
        health_status["status"] = "unhealthy"
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status

@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    
    # This would be better with prometheus_client library
    metrics = []
    
    # System metrics
    metrics.append(f'cpu_usage_percent {psutil.cpu_percent()}')
    metrics.append(f'memory_usage_percent {psutil.virtual_memory().percent}')
    metrics.append(f'disk_usage_percent {psutil.disk_usage("/").percent}')
    
    # Application metrics (would come from actual monitoring)
    metrics.append(f'app_uptime_seconds {int(time.time() - start_time)}')
    
    return "\n".join(metrics)
