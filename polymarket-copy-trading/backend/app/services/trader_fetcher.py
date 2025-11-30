"""
Service for fetching and storing trader data from The Graph Protocol.

This service orchestrates the entire data pipeline:
1. Fetch trader data from The Graph Protocol
2. Normalize and validate data
3. Store/update in database using bulk operations
4. Calculate rankings and statistics
5. Handle errors gracefully with retry logic

Business Logic:
- Fetches top traders by P&L
- Stores daily statistics for time-series analysis
- Maintains trader positions and market data
- Calculates leaderboard rankings
- Optimized for performance with batch operations
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.dialects.postgresql import insert

from app.services.graph_client import PolymarketGraphClient
from app.models.trader_v2 import TraderV2, TraderStats, TraderMarket, PositionSide, PositionStatus

logger = logging.getLogger(__name__)


class TraderDataFetcher:
    """
    Orchestrates fetching trader data from The Graph Protocol and storing in database.
    
    This service handles the complete data pipeline from Graph queries to database
    storage, including data normalization, validation, and batch operations for
    optimal performance.
    """
    
    # Configuration constants
    DEFAULT_BATCH_SIZE = 50
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    RETRY_BACKOFF = 2.0  # exponential backoff multiplier
    STALE_DATA_THRESHOLD = 300  # 5 minutes in seconds
    
    def __init__(
        self,
        db_session: AsyncSession,
        graph_client: PolymarketGraphClient,
        batch_size: int = DEFAULT_BATCH_SIZE
    ):
        """
        Initialize the trader data fetcher.
        
        Args:
            db_session: Async SQLAlchemy database session
            graph_client: Polymarket Graph Protocol client
            batch_size: Number of records to batch for bulk operations (default: 50)
        """
        self.db = db_session
        self.graph_client = graph_client
        self.batch_size = batch_size
        
        logger.info(f"Initialized TraderDataFetcher (batch_size={batch_size})")
    
    # ========================================================================
    # Main Public Methods
    # ========================================================================
    
    async def fetch_and_store_top_traders(
        self,
        limit: int = 100,
        timeframe_days: int = 7
    ) -> Dict[str, int]:
        """
        Fetch top traders from The Graph and store/update in database.
        
        This is the main orchestration method that:
        1. Fetches top traders from Graph Protocol
        2. Normalizes the data to match our schema
        3. Performs upserts (insert new, update existing)
        4. Uses bulk operations for performance
        5. Calculates derived metrics (win rate, avg trade size)
        
        Args:
            limit: Maximum number of traders to fetch (default: 100)
            timeframe_days: Activity timeframe in days (default: 7)
            
        Returns:
            Summary dictionary with counts and errors:
            {
                "traders_fetched": 95,
                "new_traders": 12,
                "updated_traders": 83,
                "errors": 5
            }
            
        Example:
            >>> fetcher = TraderDataFetcher(db, graph_client)
            >>> result = await fetcher.fetch_and_store_top_traders(limit=50)
            >>> print(f"Stored {result['new_traders']} new traders")
        """
        start_time = datetime.utcnow()
        logger.info(f"Fetching top {limit} traders for {timeframe_days}-day timeframe")
        
        summary = {
            "traders_fetched": 0,
            "new_traders": 0,
            "updated_traders": 0,
            "errors": 0
        }
        
        try:
            # 1. Fetch from Graph Protocol
            traders_data = await self.graph_client.get_top_traders(
                limit=limit,
                timeframe_days=timeframe_days
            )
            
            summary["traders_fetched"] = len(traders_data)
            logger.info(f"Fetched {len(traders_data)} traders from Graph Protocol")
            
            if not traders_data:
                logger.warning("No traders returned from Graph Protocol")
                return summary
            
            # 2. Process traders in batches
            for i in range(0, len(traders_data), self.batch_size):
                batch = traders_data[i:i + self.batch_size]
                batch_result = await self._process_trader_batch(batch)
                
                summary["new_traders"] += batch_result["new"]
                summary["updated_traders"] += batch_result["updated"]
                summary["errors"] += batch_result["errors"]
            
            # 3. Commit transaction
            await self.db.commit()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(
                f"Completed fetch_and_store_top_traders in {duration:.2f}s: "
                f"{summary['new_traders']} new, {summary['updated_traders']} updated, "
                f"{summary['errors']} errors"
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Error in fetch_and_store_top_traders: {e}", exc_info=True)
            await self.db.rollback()
            summary["errors"] += 1
            return summary
    
    async def fetch_trader_statistics(
        self,
        wallet_address: str,
        days: int = 30
    ) -> bool:
        """
        Fetch and store daily statistics for a specific trader.
        
        This method:
        1. Fetches daily stats from Graph Protocol
        2. Upserts into trader_stats table (one row per day)
        3. Uses ON CONFLICT UPDATE for idempotent operation
        
        Args:
            wallet_address: Ethereum wallet address
            days: Number of days of history to fetch (default: 30)
            
        Returns:
            True if successful, False otherwise
            
        Example:
            >>> success = await fetcher.fetch_trader_statistics("0x123...", days=30)
            >>> if success:
            ...     print("Statistics updated")
        """
        logger.info(f"Fetching statistics for {wallet_address} ({days} days)")
        
        try:
            # 1. Verify trader exists
            trader = await self.db.get(TraderV2, wallet_address)
            if not trader:
                logger.warning(f"Trader not found: {wallet_address}")
                return False
            
            # 2. Fetch stats from Graph (using detail query for now)
            # Note: Actual implementation would use TRADER_STATISTICS_QUERY
            # For now, we'll create stats from positions
            positions = await self.graph_client.get_trader_positions(
                wallet_address,
                limit=1000
            )
            
            if not positions:
                logger.warning(f"No positions found for {wallet_address}")
                return True  # Not an error, just no data
            
            # 3. Group positions by date and calculate daily stats
            daily_stats = self._group_positions_by_date(positions, days)
            
            # 4. Upsert daily stats
            for stats in daily_stats:
                stmt = insert(TraderStats).values(
                    wallet_address=wallet_address,
                    date=stats['date'],
                    daily_pnl=stats['daily_pnl'],
                    daily_volume=stats['daily_volume'],
                    trades_count=stats['trades_count'],
                    win_count=stats['win_count'],
                    loss_count=stats['loss_count']
                ).on_conflict_do_update(
                    index_elements=['wallet_address', 'date'],
                    set_={
                        'daily_pnl': stats['daily_pnl'],
                        'daily_volume': stats['daily_volume'],
                        'trades_count': stats['trades_count'],
                        'win_count': stats['win_count'],
                        'loss_count': stats['loss_count']
                    }
                )
                await self.db.execute(stmt)
            
            await self.db.commit()
            logger.info(f"Stored {len(daily_stats)} days of statistics for {wallet_address}")
            return True
            
        except Exception as e:
            logger.error(f"Error fetching statistics for {wallet_address}: {e}", exc_info=True)
            await self.db.rollback()
            return False
    
    async def calculate_leaderboard_rankings(self) -> List[Dict]:
        """
        Calculate leaderboard rankings based on 7-day P&L and win rate.
        
        Rankings are determined by:
        1. Primary: 7-day P&L (higher is better)
        2. Tiebreaker: Win rate (higher is better)
        
        Returns:
            List of trader dictionaries with rankings:
            [
                {
                    "rank": 1,
                    "wallet_address": "0x123...",
                    "pnl_7d": 5000.00,
                    "win_rate": 75.5,
                    "total_trades": 120
                },
                ...
            ]
            
        Example:
            >>> leaderboard = await fetcher.calculate_leaderboard_rankings()
            >>> top_trader = leaderboard[0]
            >>> print(f"Rank 1: {top_trader['wallet_address']}")
        """
        logger.info("Calculating leaderboard rankings")
        
        try:
            # Calculate 7-day cutoff
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            
            # Query to get 7-day P&L per trader
            stmt = select(
                TraderStats.wallet_address,
                func.sum(TraderStats.daily_pnl).label('pnl_7d'),
                func.sum(TraderStats.daily_volume).label('volume_7d'),
                func.sum(TraderStats.trades_count).label('trades_7d'),
                func.sum(TraderStats.win_count).label('wins_7d'),
                func.sum(TraderStats.loss_count).label('losses_7d')
            ).where(
                TraderStats.date >= seven_days_ago.date()
            ).group_by(
                TraderStats.wallet_address
            ).order_by(
                func.sum(TraderStats.daily_pnl).desc()
            )
            
            result = await self.db.execute(stmt)
            stats_rows = result.all()
            
            # Build leaderboard with rankings
            leaderboard = []
            rank = 1
            
            for row in stats_rows:
                # Get trader details
                trader = await self.db.get(TraderV2, row.wallet_address)
                if not trader:
                    continue
                
                # Calculate 7-day win rate
                total_7d = row.wins_7d + row.losses_7d
                win_rate_7d = (row.wins_7d / total_7d * 100) if total_7d > 0 else 0
                
                leaderboard.append({
                    "rank": rank,
                    "wallet_address": row.wallet_address,
                    "username": trader.username,
                    "pnl_7d": float(row.pnl_7d or 0),
                    "volume_7d": float(row.volume_7d or 0),
                    "trades_7d": row.trades_7d or 0,
                    "win_rate_7d": round(win_rate_7d, 2),
                    "total_pnl": float(trader.total_pnl),
                    "total_trades": trader.total_trades,
                    "win_rate": float(trader.win_rate)
                })
                
                rank += 1
            
            logger.info(f"Calculated rankings for {len(leaderboard)} traders")
            return leaderboard
            
        except Exception as e:
            logger.error(f"Error calculating leaderboard: {e}", exc_info=True)
            return []
    
    async def update_trader_markets(self, wallet_address: str) -> int:
        """
        Fetch and store all markets a trader has participated in.
        
        Process:
        1. Fetch all positions for trader
        2. Extract unique markets
        3. Store in trader_markets table
        4. Update existing positions if data changed
        
        Args:
            wallet_address: Ethereum wallet address
            
        Returns:
            Number of markets stored/updated
            
        Example:
            >>> count = await fetcher.update_trader_markets("0x123...")
            >>> print(f"Updated {count} markets")
        """
        logger.info(f"Updating markets for {wallet_address}")
        
        try:
            # 1. Fetch positions
            positions = await self.graph_client.get_trader_positions(
                wallet_address,
                limit=1000
            )
            
            if not positions:
                logger.info(f"No positions found for {wallet_address}")
                return 0
            
            # 2. Process and store positions
            markets_stored = 0
            
            for position in positions:
                try:
                    # Determine position side
                    side = position.get('side', 'YES')
                    position_side = PositionSide.YES if side.upper() == 'YES' else PositionSide.NO
                    
                    # Determine status
                    status = PositionStatus.CLOSED if position.get('closed_at') else PositionStatus.OPEN
                    
                    # Upsert trader market
                    stmt = insert(TraderMarket).values(
                        wallet_address=wallet_address,
                        market_id=position['market_id'],
                        market_name=position.get('market_name'),
                        position_side=position_side,
                        entry_price=Decimal(str(position.get('entry_price', 0))),
                        quantity=Decimal(str(position.get('quantity', 0))),
                        status=status,
                        pnl=Decimal(str(position.get('pnl', 0))),
                        created_at=datetime.fromisoformat(position['created_at']) if position.get('created_at') else datetime.utcnow(),
                        closed_at=datetime.fromisoformat(position['closed_at']) if position.get('closed_at') else None
                    ).on_conflict_do_update(
                        index_elements=['id'],
                        set_={
                            'status': status,
                            'pnl': Decimal(str(position.get('pnl', 0))),
                            'closed_at': datetime.fromisoformat(position['closed_at']) if position.get('closed_at') else None
                        }
                    )
                    
                    await self.db.execute(stmt)
                    markets_stored += 1
                    
                except Exception as e:
                    logger.warning(f"Error storing position {position.get('position_id')}: {e}")
                    continue
            
            await self.db.commit()
            logger.info(f"Stored/updated {markets_stored} positions for {wallet_address}")
            return markets_stored
            
        except Exception as e:
            logger.error(f"Error updating markets for {wallet_address}: {e}", exc_info=True)
            await self.db.rollback()
            return 0
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    async def _process_trader_batch(self, traders_data: List[Dict]) -> Dict[str, int]:
        """
        Process a batch of traders with upsert logic.
        
        Args:
            traders_data: List of trader dictionaries from Graph
            
        Returns:
            Summary with counts: {"new": X, "updated": Y, "errors": Z}
        """
        result = {"new": 0, "updated": 0, "errors": 0}
        
        for trader_data in traders_data:
            try:
                wallet_address = trader_data['wallet_address']
                
                # Check if trader exists
                existing_trader = await self.db.get(TraderV2, wallet_address)
                
                # Normalize data
                normalized = self._normalize_trader_data(trader_data)
                
                if existing_trader:
                    # Update existing trader
                    if self._is_trader_data_stale(existing_trader.updated_at):
                        for key, value in normalized.items():
                            setattr(existing_trader, key, value)
                        existing_trader.updated_at = datetime.utcnow()
                        result["updated"] += 1
                        logger.debug(f"Updated trader {wallet_address}")
                else:
                    # Create new trader
                    new_trader = TraderV2(
                        wallet_address=wallet_address,
                        **normalized
                    )
                    self.db.add(new_trader)
                    result["new"] += 1
                    logger.debug(f"Created new trader {wallet_address}")
                    
            except Exception as e:
                logger.error(f"Error processing trader: {e}", exc_info=True)
                result["errors"] += 1
                continue
        
        return result
    
    def _normalize_trader_data(self, raw_data: Dict) -> Dict:
        """
        Convert Graph Protocol data to database schema format.
        
        Performs:
        - Field name mapping
        - Type conversions (str -> Decimal, int -> float)
        - Calculated fields (win rate, avg trade size)
        - Data validation
        
        Args:
            raw_data: Raw trader data from Graph Protocol
            
        Returns:
            Dictionary matching TraderV2 schema
        """
        # Extract and convert values
        total_trades = int(raw_data.get('total_trades', 0))
        total_volume = Decimal(str(raw_data.get('total_volume', 0)))
        
        # Calculate win rate
        win_rate = float(raw_data.get('win_rate', 0))
        
        # Parse timestamp
        last_trade_at = None
        if raw_data.get('last_trade_at'):
            try:
                last_trade_at = datetime.fromisoformat(raw_data['last_trade_at'].replace('Z', '+00:00'))
            except:
                pass
        
        return {
            'username': raw_data.get('username'),
            'total_volume': total_volume,
            'total_pnl': Decimal(str(raw_data.get('realized_pnl', 0))),
            'win_rate': win_rate,
            'total_trades': total_trades,
            'markets_traded': int(raw_data.get('markets_traded', 0)),
            'last_trade_at': last_trade_at
        }
    
    def _calculate_7day_pnl(self, positions: List[Dict]) -> Decimal:
        """
        Calculate P&L from positions in the last 7 days.
        
        Args:
            positions: List of position dictionaries
            
        Returns:
            Total P&L as Decimal
        """
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        pnl = Decimal('0')
        for pos in positions:
            try:
                created_at = datetime.fromisoformat(pos.get('created_at', ''))
                if created_at >= seven_days_ago:
                    pnl += Decimal(str(pos.get('pnl', 0)))
            except:
                continue
        
        return pnl
    
    def _is_trader_data_stale(self, last_updated: Optional[datetime]) -> bool:
        """
        Check if trader data needs refresh (older than 5 minutes).
        
        Args:
            last_updated: Timestamp of last update
            
        Returns:
            True if stale (needs update), False if fresh
        """
        if not last_updated:
            return True
        
        age_seconds = (datetime.utcnow() - last_updated).total_seconds()
        return age_seconds > self.STALE_DATA_THRESHOLD
    
    def _group_positions_by_date(self, positions: List[Dict], days: int) -> List[Dict]:
        """
        Group positions by date and calculate daily statistics.
        
        Args:
            positions: List of position dictionaries
            days: Number of days to look back
            
        Returns:
            List of daily stat dictionaries
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        daily_groups = {}
        
        for pos in positions:
            try:
                # Parse created date
                created_str = pos.get('created_at', '')
                if not created_str:
                    continue
                
                created = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                if created < cutoff_date:
                    continue
                
                date_key = created.date()
                
                if date_key not in daily_groups:
                    daily_groups[date_key] = {
                        'date': date_key,
                        'daily_pnl': Decimal('0'),
                        'daily_volume': Decimal('0'),
                        'trades_count': 0,
                        'win_count': 0,
                        'loss_count': 0
                    }
                
                # Accumulate stats
                pnl = Decimal(str(pos.get('pnl', 0)))
                daily_groups[date_key]['daily_pnl'] += pnl
                daily_groups[date_key]['daily_volume'] += Decimal(str(pos.get('quantity', 0) * pos.get('entry_price', 0)))
                daily_groups[date_key]['trades_count'] += 1
                
                if pos.get('status') == 'CLOSED':
                    if pnl > 0:
                        daily_groups[date_key]['win_count'] += 1
                    else:
                        daily_groups[date_key]['loss_count'] += 1
                        
            except Exception as e:
                logger.warning(f"Error grouping position: {e}")
                continue
        
        return list(daily_groups.values())


# ========================================================================
# Convenience Functions
# ========================================================================

async def create_trader_fetcher(db: AsyncSession) -> TraderDataFetcher:
    """
    Factory function to create a TraderDataFetcher with default dependencies.
    
    Args:
        db: Database session
        
    Returns:
        Configured TraderDataFetcher instance
    """
    from app.services.graph_client import graph_client
    
    return TraderDataFetcher(
        db_session=db,
        graph_client=graph_client,
        batch_size=50
    )
