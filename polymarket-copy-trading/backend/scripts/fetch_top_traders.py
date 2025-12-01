import asyncio
import sys
import os
import logging
from datetime import datetime

# Add backend directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import async_session, engine
from app.services.trader_fetcher import TraderDataFetcher
from app.services.graph_client import graph_client
from app.models.trader_v2 import TraderV2
from app.db.base import Base
from sqlalchemy import select
from sqlalchemy import select, desc

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def create_trader_fetcher(db):
    """Helper function to create and initialize TraderDataFetcher."""
    fetcher = TraderDataFetcher(db, graph_client)
    # await fetcher.initialize_markets()
    return fetcher

async def main():
    """Main execution function."""
    logger.info("Starting manual fetch of Top Traders and Biggest Trades...")
    
    try:
        # Create database tables if they don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as db:
            fetcher = await create_trader_fetcher(db)
            
            print("\n=== Fetching Top Traders of Today (24h) ===")
            # Fetch top traders for the last 24 hours
            summary = await fetcher.fetch_and_store_top_traders(limit=10, timeframe_days=1)
            print(f"Fetch completed: {summary}")
            
            # Display Top Traders
            print("\n=== Top 10 Traders by Volume (Today) ===")
            print(f"{'Rank':<5} {'Wallet Address':<42} {'Volume (24h)':<15} {'P&L (24h)':<15} {'Win Rate':<10}")
            print("-" * 90)
            
            # Query DB for today's top traders (sorted by volume for "liquidity")
            stmt = select(TraderV2).order_by(desc(TraderV2.total_volume)).limit(10)
            result = await db.execute(stmt)
            top_traders = result.scalars().all()
            
            for i, trader in enumerate(top_traders, 1):
                print(f"{i:<5} {trader.wallet_address:<42} ${float(trader.total_volume):<14,.2f} ${float(trader.total_pnl):<14,.2f} {float(trader.win_rate):.1f}%")

            print("\n=== Fetching Biggest Trades of Today ===")
            # Fetch biggest trades
            biggest_trades = await fetcher.graph_client.get_biggest_trades(limit=10, timeframe_days=1)
            
            print("\n=== Biggest Trades (Today) ===")
            print(f"{'Market':<40} {'Type':<5} {'Amount':<15} {'Price':<8} {'Trader':<15}")
            print("-" * 90)
            
            for trade in biggest_trades:
                market_question = trade.get('market', {}).get('question', 'Unknown Market')[:38]
                outcome = trade.get('outcome', 'YES')
                amount = float(trade.get('amount', 0))
                price = float(trade.get('entryPrice', 0))
                trader_addr = trade.get('user', {}).get('address', 'Unknown')
                
                print(f"{market_question:<40} {outcome:<5} ${amount:<14,.2f} ${price:<7.2f} {trader_addr[:10]}...")

    except Exception as e:
        logger.error(f"Script failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Cleanup
        await graph_client.close()
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
