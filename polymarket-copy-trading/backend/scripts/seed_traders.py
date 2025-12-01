"""
One-time script to seed initial trader data from The Graph Protocol.

This script fetches top traders and populates the database for initial setup.

Usage:
    python -m scripts.seed_traders
    
    # Or with custom parameters
    python -m scripts.seed_traders --limit 500 --days 30
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from app.core.config import settings
from app.services.graph_client import PolymarketGraphClient
from app.services.trader_fetcher import TraderDataFetcher
from app.models.trader_v2 import TraderV2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def seed_initial_traders(limit: int = 500, timeframe_days: int = 30):
    """
    Seed initial trader data from The Graph Protocol.
    
    Args:
        limit: Number of top traders to fetch (default: 500)
        timeframe_days: Activity timeframe in days (default: 30)
    """
    logger.info(f"Starting trader data seeding (limit={limit}, days={timeframe_days})")
    
    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as db:
            # Initialize clients
            graph_client = PolymarketGraphClient()
            fetcher = TraderDataFetcher(
                db_session=db,
                graph_client=graph_client,
                batch_size=100  # Larger batches for initial seed
            )
            
            # Check if data already exists
            stmt = select(func.count()).select_from(TraderV2)
            result = await db.execute(stmt)
            existing_count = result.scalar()
            
            if existing_count > 0:
                logger.warning(f"Database already has {existing_count} traders")
                response = input(f"Continue and update existing data? (y/n): ")
                if response.lower() != 'y':
                    logger.info("Seeding cancelled")
                    return
            
            # Fetch and store traders
            logger.info("Fetching top traders from The Graph...")
            result = await fetcher.fetch_and_store_top_traders(
                limit=limit,
                timeframe_days=timeframe_days
            )
            
            # Print summary
            logger.info("=" * 60)
            logger.info("Seeding Summary:")
            logger.info(f"  Traders Fetched: {result['traders_fetched']}")
            logger.info(f"  New Traders:     {result['new_traders']}")
            logger.info(f"  Updated Traders: {result['updated_traders']}")
            logger.info(f"  Errors:          {result['errors']}")
            logger.info("=" * 60)
            
            # Verify data in database
            stmt = select(func.count()).select_from(TraderV2)
            result_check = await db.execute(stmt)
            final_count = result_check.scalar()
            
            logger.info(f"Total traders in database: {final_count}")
            
            # Fetch statistics for top 100 traders
            if result['traders_fetched'] > 0:
                logger.info("\nFetching statistics for top 100 traders...")
                
                stmt = select(TraderV2).order_by(TraderV2.total_pnl.desc()).limit(100)
                top_traders_result = await db.execute(stmt)
                top_traders = top_traders_result.scalars().all()
                
                stats_success = 0
                stats_failed = 0
                
                for idx, trader in enumerate(top_traders, 1):
                    try:
                        logger.info(f"  [{idx}/100] Fetching stats for {trader.wallet_address[:10]}...")
                        success = await fetcher.fetch_trader_statistics(
                            trader.wallet_address,
                            days=30
                        )
                        if success:
                            stats_success += 1
                        else:
                            stats_failed += 1
                    except Exception as e:
                        logger.error(f"  Error fetching stats: {e}")
                        stats_failed += 1
                
                logger.info(f"\nStatistics: {stats_success} success, {stats_failed} failed")
            
            # Calculate initial leaderboard
            logger.info("\nCalculating initial leaderboard...")
            leaderboard = await fetcher.calculate_leaderboard_rankings()
            logger.info(f"Leaderboard calculated with {len(leaderboard)} traders")
            
            # Show top 10
            if leaderboard:
                logger.info("\nTop 10 Traders:")
                logger.info("-" * 80)
                logger.info(f"{'Rank':<6} {'Address':<45} {'P&L 7d':<15} {'Win Rate':<10}")
                logger.info("-" * 80)
                for trader in leaderboard[:10]:
                    logger.info(
                        f"{trader['rank']:<6} "
                        f"{trader['wallet_address']:<45} "
                        f"${trader['pnl_7d']:<14.2f} "
                        f"{trader['win_rate_7d']:<9.2f}%"
                    )
                logger.info("-" * 80)
            
            logger.info("\n✅ Seeding completed successfully!")
            
    except Exception as e:
        logger.error(f"Error during seeding: {e}", exc_info=True)
        raise
    
    finally:
        await engine.dispose()


async def verify_data():
    """Verify seeded data integrity."""
    logger.info("Verifying seeded data...")
    
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    try:
        async with async_session() as db:
            # Check traders count
            stmt = select(func.count()).select_from(TraderV2)
            result = await db.execute(stmt)
            count = result.scalar()
            logger.info(f"✓ Total traders: {count}")
            
            # Check for traders with stats
            from app.models.trader_v2 import TraderStats
            stmt = select(func.count(func.distinct(TraderStats.wallet_address)))
            result = await db.execute(stmt)
            stats_count = result.scalar()
            logger.info(f"✓ Traders with statistics: {stats_count}")
            
            # Check for traders with positions
            from app.models.trader_v2 import TraderMarket
            stmt = select(func.count(func.distinct(TraderMarket.wallet_address)))
            result = await db.execute(stmt)
            positions_count = result.scalar()
            logger.info(f"✓ Traders with positions: {positions_count}")
            
            # Show sample trader
            stmt = select(TraderV2).order_by(TraderV2.total_pnl.desc()).limit(1)
            result = await db.execute(stmt)
            top_trader = result.scalars().first()
            
            if top_trader:
                logger.info(f"\nTop Trader:")
                logger.info(f"  Address: {top_trader.wallet_address}")
                logger.info(f"  Total P&L: ${top_trader.total_pnl}")
                logger.info(f"  Win Rate: {top_trader.win_rate}%")
                logger.info(f"  Total Trades: {top_trader.total_trades}")
            
    finally:
        await engine.dispose()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Seed trader data from The Graph')
    parser.add_argument('--limit', type=int, default=500, help='Number of traders to fetch')
    parser.add_argument('--days', type=int, default=30, help='Activity timeframe in days')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing data')
    
    args = parser.parse_args()
    
    if args.verify_only:
        await verify_data()
    else:
        await seed_initial_traders(limit=args.limit, timeframe_days=args.days)
        await verify_data()


if __name__ == "__main__":
    asyncio.run(main())
