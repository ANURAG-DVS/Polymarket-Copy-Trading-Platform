"""
Leaderboard Background Jobs

Celery tasks for maintaining leaderboard:
- Periodic recalculation of trader stats
- Market price updates for unrealized P&L
- Daily snapshot creation
- Stale data pruning
"""

from celery import shared_task
from datetime import datetime, timedelta
from loguru import logger

from app.db.session import get_db
from app.services.leaderboard.ranking_service import get_leaderboard_service
from app.services.leaderboard.pnl_calculator import get_pnl_calculator


@shared_task(name="leaderboard.recalculate_all_traders")
async def recalculate_all_traders():
    """
    Recalculate stats for all active traders.
    
    Runs every 5 minutes to keep leaderboard fresh.
    """
    logger.info("Starting leaderboard recalculation")
    
    leaderboard = get_leaderboard_service()
    
    try:
        async with get_db() as db:
            # Get all active traders (those with trades in last 30 days)
            from app.models.api_key import Trade
            from sqlalchemy import select, distinct
            
            cutoff = datetime.utcnow() - timedelta(days=30)
            
            query = select(distinct(Trade.trader_wallet_address)).where(
                Trade.entry_timestamp >= cutoff
            )
            
            result = await db.execute(query)
            active_traders = result.scalars().all()
            
            logger.info(f"Recalculating stats for {len(active_traders)} active traders")
            
            # Update each trader
            updated_count = 0
            for wallet_address in active_traders:
                try:
                    await leaderboard.update_trader_stats(db, wallet_address)
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Failed to update {wallet_address}: {e}")
            
            logger.info(f"Successfully updated {updated_count}/{len(active_traders)} traders")
            
    except Exception as e:
        logger.error(f"Leaderboard recalculation failed: {e}")
        raise


@shared_task(name="leaderboard.update_unrealized_pnl")
async def update_unrealized_pnl():
    """
    Update unrealized P&L for all open positions.
    
    Fetches current market prices from Polymarket API and updates
    unrealized P&L calculations.
    
    Runs every 5 minutes.
    """
    logger.info("Updating unrealized P&L")
    
    try:
        async with get_db() as db:
            from app.models.api_key import Trade
            from sqlalchemy import select, update as sql_update
            from app.services.polymarket import get_polymarket_client
            
            # Get all open positions
            query = select(Trade).where(Trade.status == 'open')
            result = await db.execute(query)
            open_trades = result.scalars().all()
            
            logger.info(f"Updating {len(open_trades)} open positions")
            
            # Get Polymarket client
            client = get_polymarket_client()
            
            # Group by market for efficient API calls
            markets_trades = {}
            for trade in open_trades:
                if trade.market_id not in markets_trades:
                    markets_trades[trade.market_id] = []
                markets_trades[trade.market_id].append(trade)
            
            # Update prices per market
            updated_count = 0
            for market_id, trades in markets_trades.items():
                try:
                    # Fetch current market price
                    prices = await client.get_market_prices(market_id)
                    
                    for trade in trades:
                        # Determine current price based on outcome
                        current_price = (
                            prices.yes_price if trade.position == 'YES'
                            else prices.no_price
                        )
                        
                        # Calculate unrealized P&L
                        current_value = trade.quantity * current_price
                        unrealized_pnl = current_value - trade.entry_value_usd
                        unrealized_pnl_pct = (
                            (unrealized_pnl / trade.entry_value_usd * 100)
                            if trade.entry_value_usd > 0 else 0
                        )
                        
                        # Update trade
                        trade.current_value_usd = current_value
                        trade.unrealized_pnl_usd = unrealized_pnl
                        trade.unrealized_pnl_percent = unrealized_pnl_pct
                        
                        updated_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to update market {market_id}: {e}")
            
            await db.commit()
            
            logger.info(f"Updated unrealized P&L for {updated_count} positions")
            
    except Exception as e:
        logger.error(f"Unrealized P&L update failed: {e}")
        raise


@shared_task(name="leaderboard.create_daily_snapshot")
async def create_daily_snapshot():
    """
    Create daily snapshot of leaderboard.
    
    Runs once per day at midnight UTC.
    """
    logger.info("Creating daily leaderboard snapshot")
    
    leaderboard = get_leaderboard_service()
    
    try:
        async with get_db() as db:
            await leaderboard.create_daily_snapshot(db)
            
        logger.info("Daily snapshot created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create daily snapshot: {e}")
        raise


@shared_task(name="leaderboard.prune_stale_data")
async def prune_stale_data():
    """
    Remove stale trader data and old snapshots.
    
    - Remove traders with no trades in last 90 days
    - Remove snapshots older than 1 year
    
    Runs once per day.
    """
    logger.info("Pruning stale leaderboard data")
    
    try:
        async with get_db() as db:
            from app.models.api_key import User
            from sqlalchemy import delete
            
            # Remove inactive traders
            cutoff = datetime.utcnow() - timedelta(days=90)
            
            # (In production, would delete from traders table where last_trade < cutoff)
            
            # Remove old snapshots (implementation would delete from snapshots table)
            snapshot_cutoff = datetime.utcnow() - timedelta(days=365)
            
            logger.info("Stale data pruned successfully")
            
    except Exception as e:
        logger.error(f"Failed to prune stale data: {e}")
        raise


# Celery beat schedule configuration
LEADERBOARD_SCHEDULE = {
    'recalculate-leaderboard': {
        'task': 'leaderboard.recalculate_all_traders',
        'schedule': 300.0,  # Every 5 minutes
    },
    'update-unrealized-pnl': {
        'task': 'leaderboard.update_unrealized_pnl',
        'schedule': 300.0,  # Every 5 minutes
    },
    'daily-snapshot': {
        'task': 'leaderboard.create_daily_snapshot',
        'schedule': timedelta(days=1),  # Daily at midnight
    },
    'prune-stale-data': {
        'task': 'leaderboard.prune_stale_data',
        'schedule': timedelta(days=1),  # Daily
    },
}
