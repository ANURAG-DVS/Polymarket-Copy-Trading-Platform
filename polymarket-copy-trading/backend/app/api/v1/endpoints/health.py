from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from app.db.session import get_db
from app.core.config import settings
import httpx
import time
import psutil
from datetime import datetime, timedelta
import redis.asyncio as aioredis

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

@router.get("/health/traders")
async def traders_health_check(db: AsyncSession = Depends(get_db)):
    """
    Check if trader data is fresh and accessible.
    
    Returns:
        Health status with trader data freshness information
    """
    from app.models.trader_v2 import TraderV2, TraderStats
    
    health_status = {
        "status": "healthy",
        "service": "trader-data",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }
    
    all_healthy = True
    
    try:
        # Check trader count
        stmt = select(func.count()).select_from(TraderV2)
        result = await db.execute(stmt)
        traders_count = result.scalar()
        
        health_status["traders_count"] = traders_count
        
        if traders_count == 0:
            all_healthy = False
            health_status["checks"]["trader_count"] = {
                "status": "warning",
                "message": "No traders in database"
            }
        else:
            health_status["checks"]["trader_count"] = {
                "status": "healthy",
                "count": traders_count
            }
        
        # Check most recent update
        stmt = select(func.max(TraderV2.updated_at))
        result = await db.execute(stmt)
        last_update = result.scalar()
        
        if last_update:
            age_minutes = (datetime.utcnow() - last_update).total_seconds() / 60
            health_status["last_update"] = last_update.isoformat()
            health_status["last_update_minutes_ago"] = round(age_minutes, 2)
            
            # Alert if data is stale (>10 minutes)
            if age_minutes > 10:
                all_healthy = False
                health_status["checks"]["data_freshness"] = {
                    "status": "warning",
                    "message": f"Trader data is {age_minutes:.1f} minutes old (threshold: 10 min)",
                    "last_update": last_update.isoformat()
                }
            else:
                health_status["checks"]["data_freshness"] = {
                    "status": "healthy",
                    "last_update": last_update.isoformat(),
                    "age_minutes": round(age_minutes, 2)
                }
        else:
            all_healthy = False
            health_status["checks"]["data_freshness"] = {
                "status": "warning",
                "message": "No trader updates found"
            }
        
        # Check Redis cache connectivity
        try:
            cache = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await cache.ping()
            await cache.close()
            
            health_status["checks"]["cache"] = {
                "status": "healthy",
                "message": "Redis cache accessible"
            }
        except Exception as e:
            all_healthy = False
            health_status["checks"]["cache"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check if we have recent statistics
        stmt = select(func.count()).select_from(TraderStats).where(
            TraderStats.date >= (datetime.utcnow() - timedelta(days=7)).date()
        )
        result = await db.execute(stmt)
        recent_stats_count = result.scalar()
        
        health_status["recent_stats_count"] = recent_stats_count
        
        if recent_stats_count > 0:
            health_status["checks"]["statistics"] = {
                "status": "healthy",
                "recent_entries": recent_stats_count
            }
        else:
            health_status["checks"]["statistics"] = {
                "status": "warning",
                "message": "No recent statistics (last 7 days)"
            }
        
    except Exception as e:
        all_healthy = False
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Set overall status
    if not all_healthy:
        health_status["status"] = "degraded"
    
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
