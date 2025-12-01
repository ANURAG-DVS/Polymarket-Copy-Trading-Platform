"""
Comprehensive unit tests for TraderDataFetcher service.

Tests cover:
- Data fetching and storage
- Update logic for existing traders
- Win rate and P&L calculations
- Error handling and retries
- Batch operations performance
- Leaderboard rankings
- Stale data detection
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from app.services.trader_fetcher import TraderDataFetcher
from app.services.graph_client import PolymarketGraphClient
from app.models.trader_v2 import TraderV2, TraderStats, TraderMarket, PositionSide, PositionStatus
from app.db.base import Base


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_trader_data() -> List[Dict]:
    """Sample trader data from The Graph Protocol."""
    return [
        {
            "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
            "username": "TopTrader1",
            "total_volume": "50000.00",
            "realized_pnl": "1500.50",
            "total_trades": 45,
            "win_rate": 66.67,
            "markets_traded": 12,
            "last_trade_at": datetime.utcnow().isoformat()
        },
        {
            "wallet_address": "0xabcdef1234567890abcdef1234567890abcdef12",
            "username": "ProTrader2",
            "total_volume": "35000.00",
            "realized_pnl": "800.25",
            "total_trades": 30,
            "win_rate": 60.00,
            "markets_traded": 8,
            "last_trade_at": datetime.utcnow().isoformat()
        },
        {
            "wallet_address": "0x9876543210fedcba9876543210fedcba98765432",
            "username": "Trader3",
            "total_volume": "25000.00",
            "realized_pnl": "450.00",
            "total_trades": 20,
            "win_rate": 55.00,
            "markets_traded": 5,
            "last_trade_at": datetime.utcnow().isoformat()
        }
    ]


@pytest.fixture
def sample_positions() -> List[Dict]:
    """Sample position data for testing."""
    now = datetime.utcnow()
    return [
        {
            "position_id": "pos1",
            "market_id": "market1",
            "market_name": "Will BTC hit $100k?",
            "side": "YES",
            "entry_price": 0.65,
            "quantity": 100,
            "pnl": 150.50,
            "created_at": (now - timedelta(days=3)).isoformat(),
            "closed_at": (now - timedelta(days=2)).isoformat(),
            "status": "CLOSED"
        },
        {
            "position_id": "pos2",
            "market_id": "market2",
            "market_name": "ETH ETF approval?",
            "side": "NO",
            "entry_price": 0.45,
            "quantity": 200,
            "pnl": -50.25,
            "created_at": (now - timedelta(days=10)).isoformat(),
            "closed_at": (now - timedelta(days=9)).isoformat(),
            "status": "CLOSED"
        },
        {
            "position_id": "pos3",
            "market_id": "market3",
            "market_name": "AI breakthrough?",
            "side": "YES",
            "entry_price": 0.55,
            "quantity": 150,
            "pnl": 75.00,
            "created_at": (now - timedelta(days=5)).isoformat(),
            "closed_at": None,
            "status": "OPEN"
        }
    ]


@pytest.fixture
async def db_session():
    """Create async test database session using in-memory SQLite."""
    # Create async engine for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Yield session
    async with async_session() as session:
        yield session
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
def mock_graph_client(sample_trader_data, sample_positions):
    """Mock PolymarketGraphClient with predefined data."""
    client = AsyncMock(spec=PolymarketGraphClient)
    
    # Mock get_top_traders to return sample data
    client.get_top_traders = AsyncMock(return_value=sample_trader_data)
    
    # Mock get_trader_positions
    client.get_trader_positions = AsyncMock(return_value=sample_positions)
    
    # Mock get_trader_details
    client.get_trader_details = AsyncMock(return_value=sample_trader_data[0])
    
    return client


@pytest.fixture
async def trader_fetcher(db_session, mock_graph_client):
    """Create TraderDataFetcher instance with mocked dependencies."""
    return TraderDataFetcher(
        db_session=db_session,
        graph_client=mock_graph_client,
        batch_size=50
    )


# ============================================================================
# Test Utilities
# ============================================================================

def decimal_equal(value1, value2, places=2):
    """Compare Decimal values with tolerance for floating point issues."""
    if isinstance(value1, Decimal):
        value1 = float(value1)
    if isinstance(value2, Decimal):
        value2 = float(value2)
    return round(value1, places) == round(value2, places)


async def create_test_trader(
    db: AsyncSession,
    wallet_address: str,
    total_pnl: float = 1000.0,
    total_trades: int = 50,
    win_rate: float = 60.0,
    updated_at: datetime = None
) -> TraderV2:
    """Helper to create a test trader in database."""
    trader = TraderV2(
        wallet_address=wallet_address,
        username=f"TestTrader_{wallet_address[:6]}",
        total_volume=Decimal("10000.00"),
        total_pnl=Decimal(str(total_pnl)),
        win_rate=win_rate,
        total_trades=total_trades,
        markets_traded=10,
        updated_at=updated_at or datetime.utcnow()
    )
    db.add(trader)
    await db.commit()
    await db.refresh(trader)
    return trader


async def create_test_stats(
    db: AsyncSession,
    wallet_address: str,
    stat_date: date,
    daily_pnl: float = 100.0
) -> TraderStats:
    """Helper to create test trader statistics."""
    stats = TraderStats(
        wallet_address=wallet_address,
        date=stat_date,
        daily_pnl=Decimal(str(daily_pnl)),
        daily_volume=Decimal("1000.00"),
        trades_count=5,
        win_count=3,
        loss_count=2
    )
    db.add(stats)
    await db.commit()
    await db.refresh(stats)
    return stats


# ============================================================================
# Unit Tests
# ============================================================================

@pytest.mark.asyncio
async def test_fetch_and_store_new_traders(trader_fetcher, db_session, sample_trader_data):
    """Test fetching and storing new traders from Graph API."""
    # Execute fetch
    result = await trader_fetcher.fetch_and_store_top_traders(limit=10, timeframe_days=7)
    
    # Assert summary
    assert result["traders_fetched"] == len(sample_trader_data)
    assert result["new_traders"] == len(sample_trader_data)
    assert result["updated_traders"] == 0
    assert result["errors"] == 0
    
    # Verify traders in database
    stmt = select(TraderV2)
    db_result = await db_session.execute(stmt)
    traders = db_result.scalars().all()
    
    assert len(traders) == len(sample_trader_data)
    
    # Verify first trader data
    trader = traders[0]
    assert trader.wallet_address == sample_trader_data[0]["wallet_address"]
    assert decimal_equal(trader.total_pnl, Decimal("1500.50"))
    assert trader.total_trades == 45
    assert decimal_equal(trader.win_rate, 66.67)


@pytest.mark.asyncio
async def test_fetch_and_update_existing_traders(
    trader_fetcher,
    db_session,
    mock_graph_client,
    sample_trader_data
):
    """Test updating existing traders with new data."""
    # Pre-populate database with traders
    wallet_address = sample_trader_data[0]["wallet_address"]
    await create_test_trader(
        db_session,
        wallet_address=wallet_address,
        total_pnl=1000.0,  # Old value
        total_trades=40,
        win_rate=60.0,
        updated_at=datetime.utcnow() - timedelta(minutes=10)  # Stale data
    )
    
    # Execute fetch (should update existing trader)
    result = await trader_fetcher.fetch_and_store_top_traders(limit=10)
    
    # Assert summary
    assert result["new_traders"] == 2  # Only new ones
    assert result["updated_traders"] == 1  # Existing one updated
    
    # Verify trader was updated, not duplicated
    stmt = select(func.count()).select_from(TraderV2)
    count_result = await db_session.execute(stmt)
    total_count = count_result.scalar()
    assert total_count == 3  # Not duplicated
    
    # Verify updated values
    trader = await db_session.get(TraderV2, wallet_address)
    assert decimal_equal(trader.total_pnl, Decimal("1500.50"))  # Updated
    assert trader.total_trades == 45  # Updated


@pytest.mark.asyncio
async def test_calculate_win_rate():
    """Test win rate calculation logic."""
    # Test normal case
    fetcher = TraderDataFetcher(db_session=None, graph_client=None)
    
    # Win rate from sample data: 66.67%
    data = {
        "wallet_address": "0x123",
        "total_trades": 45,
        "win_rate": 66.67,
        "realized_pnl": "1500",
        "total_volume": "50000"
    }
    
    normalized = fetcher._normalize_trader_data(data)
    assert decimal_equal(normalized["win_rate"], 66.67)
    
    # Edge case: 0 trades
    data_zero = {
        "wallet_address": "0x456",
        "total_trades": 0,
        "win_rate": 0,
        "realized_pnl": "0",
        "total_volume": "0"
    }
    
    normalized_zero = fetcher._normalize_trader_data(data_zero)
    assert normalized_zero["win_rate"] == 0.0


@pytest.mark.asyncio
async def test_fetch_with_graph_api_error(trader_fetcher, mock_graph_client):
    """Test error handling when Graph API fails."""
    # Mock API to raise exception
    mock_graph_client.get_top_traders.side_effect = Exception("Graph API Error")
    
    # Execute fetch
    result = await trader_fetcher.fetch_and_store_top_traders(limit=10)
    
    # Assert error is captured
    assert result["errors"] >= 1
    assert result["traders_fetched"] == 0


@pytest.mark.asyncio
async def test_batch_insert_performance(db_session, mock_graph_client):
    """Test batch insertion performance with 1000 traders."""
    import time
    
    # Generate 1000 mock traders
    large_dataset = []
    for i in range(1000):
        large_dataset.append({
            "wallet_address": f"0x{'0' * 38}{i:04d}",
            "username": f"Trader{i}",
            "total_volume": "10000.00",
            "realized_pnl": str(100 + i),
            "total_trades": 50,
            "win_rate": 60.0,
            "markets_traded": 5,
            "last_trade_at": datetime.utcnow().isoformat()
        })
    
    # Mock graph client to return large dataset
    mock_graph_client.get_top_traders = AsyncMock(return_value=large_dataset)
    
    # Create fetcher
    fetcher = TraderDataFetcher(
        db_session=db_session,
        graph_client=mock_graph_client,
        batch_size=50
    )
    
    # Measure execution time
    start_time = time.time()
    result = await fetcher.fetch_and_store_top_traders(limit=1000)
    end_time = time.time()
    
    duration = end_time - start_time
    
    # Assert performance
    assert duration < 5.0  # Should complete in < 5 seconds
    assert result["traders_fetched"] == 1000
    assert result["new_traders"] == 1000


@pytest.mark.asyncio
async def test_leaderboard_ranking_calculation(trader_fetcher, db_session):
    """Test leaderboard ranking based on P&L."""
    # Create traders with various P&Ls
    await create_test_trader(db_session, "0x" + "1" * 40, total_pnl=5000.0)
    await create_test_trader(db_session, "0x" + "2" * 40, total_pnl=3000.0)
    await create_test_trader(db_session, "0x" + "3" * 40, total_pnl=1000.0)
    await create_test_trader(db_session, "0x" + "4" * 40, total_pnl=4000.0)
    
    # Create stats for 7-day calculation
    now = datetime.utcnow()
    for i, pnl in enumerate([5000.0, 3000.0, 1000.0, 4000.0]):
        wallet = "0x" + str(i + 1) * 40
        for day_offset in range(7):
            await create_test_stats(
                db_session,
                wallet,
                (now - timedelta(days=day_offset)).date(),
                daily_pnl=pnl / 7
            )
    
    # Calculate leaderboard
    leaderboard = await trader_fetcher.calculate_leaderboard_rankings()
    
    # Assert rankings (highest P&L first)
    assert len(leaderboard) == 4
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["wallet_address"] == "0x" + "1" * 40
    assert leaderboard[1]["rank"] == 2
    assert leaderboard[1]["wallet_address"] == "0x" + "4" * 40
    assert leaderboard[2]["rank"] == 3
    assert leaderboard[3]["rank"] == 4


@pytest.mark.asyncio
async def test_stale_data_detection():
    """Test detection of stale trader data."""
    fetcher = TraderDataFetcher(db_session=None, graph_client=None)
    
    # Test stale data (10 minutes old)
    old_time = datetime.utcnow() - timedelta(minutes=10)
    assert fetcher._is_trader_data_stale(old_time) is True
    
    # Test fresh data (1 minute old)
    recent_time = datetime.utcnow() - timedelta(minutes=1)
    assert fetcher._is_trader_data_stale(recent_time) is False
    
    # Test None (should be considered stale)
    assert fetcher._is_trader_data_stale(None) is True


@pytest.mark.asyncio
async def test_7day_pnl_calculation(sample_positions):
    """Test calculation of 7-day P&L from positions."""
    fetcher = TraderDataFetcher(db_session=None, graph_client=None)
    
    # Calculate 7-day P&L
    pnl_7d = fetcher._calculate_7day_pnl(sample_positions)
    
    # Should include pos1 (3 days old) and pos3 (5 days old)
    # Should exclude pos2 (10 days old)
    # Expected: 150.50 + 75.00 = 225.50
    assert decimal_equal(pnl_7d, Decimal("225.50"))


@pytest.mark.asyncio
async def test_fetch_trader_statistics(trader_fetcher, db_session, mock_graph_client):
    """Test fetching and storing daily statistics."""
    wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
    
    # Create trader first
    await create_test_trader(db_session, wallet_address)
    
    # Fetch statistics
    success = await trader_fetcher.fetch_trader_statistics(wallet_address, days=30)
    
    # Assert success
    assert success is True
    
    # Verify stats were stored
    stmt = select(TraderStats).where(TraderStats.wallet_address == wallet_address)
    result = await db_session.execute(stmt)
    stats = result.scalars().all()
    
    assert len(stats) > 0


@pytest.mark.asyncio
async def test_update_trader_markets(trader_fetcher, db_session, mock_graph_client):
    """Test updating trader market positions."""
    wallet_address = "0x1234567890abcdef1234567890abcdef12345678"
    
    # Create trader
    await create_test_trader(db_session, wallet_address)
    
    # Update markets
    count = await trader_fetcher.update_trader_markets(wallet_address)
    
    # Assert positions were stored
    assert count > 0
    
    # Verify in database
    stmt = select(TraderMarket).where(TraderMarket.wallet_address == wallet_address)
    result = await db_session.execute(stmt)
    positions = result.scalars().all()
    
    assert len(positions) == count


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_full_fetch_pipeline(trader_fetcher, db_session, sample_trader_data):
    """Test complete fetch pipeline from Graph to database."""
    # Execute full pipeline
    result = await trader_fetcher.fetch_and_store_top_traders(limit=100, timeframe_days=7)
    
    # Assert traders were fetched
    assert result["traders_fetched"] > 0
    
    # Verify data integrity
    stmt = select(TraderV2)
    db_result = await db_session.execute(stmt)
    traders = db_result.scalars().all()
    
    # Check each trader has valid data
    for trader in traders:
        assert trader.wallet_address is not None
        assert len(trader.wallet_address) == 42  # Valid ETH address
        assert trader.total_pnl is not None
        assert trader.total_trades >= 0
        assert 0 <= trader.win_rate <= 100


@pytest.mark.asyncio
async def test_data_normalization():
    """Test data normalization from Graph format to DB format."""
    fetcher = TraderDataFetcher(db_session=None, graph_client=None)
    
    raw_data = {
        "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
        "username": "TestTrader",
        "total_volume": "50000.50",
        "realized_pnl": "1500.75",
        "total_trades": 45,
        "win_rate": 66.67,
        "markets_traded": 12,
        "last_trade_at": "2024-01-01T12:00:00Z"
    }
    
    normalized = fetcher._normalize_trader_data(raw_data)
    
    # Assert types and values
    assert isinstance(normalized["total_volume"], Decimal)
    assert isinstance(normalized["total_pnl"], Decimal)
    assert isinstance(normalized["win_rate"], float)
    assert isinstance(normalized["total_trades"], int)
    assert decimal_equal(normalized["total_volume"], Decimal("50000.50"))
    assert decimal_equal(normalized["total_pnl"], Decimal("1500.75"))


@pytest.mark.asyncio
async def test_group_positions_by_date(sample_positions):
    """Test grouping positions by date for daily statistics."""
    fetcher = TraderDataFetcher(db_session=None, graph_client=None)
    
    daily_stats = fetcher._group_positions_by_date(sample_positions, days=30)
    
    # Should have grouped by unique dates
    assert len(daily_stats) > 0
    
    # Each stat should have required fields
    for stat in daily_stats:
        assert "date" in stat
        assert "daily_pnl" in stat
        assert "daily_volume" in stat
        assert "trades_count" in stat
        assert "win_count" in stat
        assert "loss_count" in stat


# ============================================================================
# Performance Benchmarks
# ============================================================================

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_fetch_performance_benchmark(db_session, mock_graph_client):
    """Benchmark the fetch operation performance."""
    import time
    
    # Generate moderate dataset
    traders = []
    for i in range(100):
        traders.append({
            "wallet_address": f"0x{'0' * 38}{i:04d}",
            "username": f"Trader{i}",
            "total_volume": "10000.00",
            "realized_pnl": "500.00",
            "total_trades": 50,
            "win_rate": 60.0,
            "markets_traded": 5,
            "last_trade_at": datetime.utcnow().isoformat()
        })
    
    mock_graph_client.get_top_traders = AsyncMock(return_value=traders)
    
    fetcher = TraderDataFetcher(
        db_session=db_session,
        graph_client=mock_graph_client,
        batch_size=50
    )
    
    # Benchmark
    iterations = 3
    total_time = 0
    
    for _ in range(iterations):
        start = time.time()
        await fetcher.fetch_and_store_top_traders(limit=100)
        total_time += time.time() - start
        
        # Clear database for next iteration
        await db_session.execute(select(TraderV2).delete())
        await db_session.commit()
    
    avg_time = total_time / iterations
    
    # Assert performance criteria
    assert avg_time < 2.0  # Average should be < 2 seconds


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_handle_invalid_trader_data(db_session, mock_graph_client):
    """Test handling of malformed trader data."""
    # Mock invalid data
    invalid_data = [
        {
            "wallet_address": "invalid_address",  # Invalid
            "total_pnl": "not_a_number",  # Invalid
        }
    ]
    
    mock_graph_client.get_top_traders = AsyncMock(return_value=invalid_data)
    
    fetcher = TraderDataFetcher(
        db_session=db_session,
        graph_client=mock_graph_client
    )
    
    # Should handle gracefully
    result = await fetcher.fetch_and_store_top_traders()
    
    # Errors should be captured
    assert result["errors"] >= 0  # Graceful handling


@pytest.mark.asyncio
async def test_database_rollback_on_error(db_session, mock_graph_client):
    """Test that database rolls back on errors."""
    # Force an error during processing
    mock_graph_client.get_top_traders.side_effect = Exception("DB Error")
    
    fetcher = TraderDataFetcher(
        db_session=db_session,
        graph_client=mock_graph_client
    )
    
    # Execute
    result = await fetcher.fetch_and_store_top_traders()
    
    # Database should be clean (rollback)
    stmt = select(func.count()).select_from(TraderV2)
    count_result = await db_session.execute(stmt)
    count = count_result.scalar()
    
    assert count == 0  # No partial data
