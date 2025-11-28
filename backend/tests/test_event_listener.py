"""
Unit Tests for Event Listener and Trade Queue

Tests event parsing, validation, deduplication, and queue operations.
"""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import json

from app.services.blockchain.event_listener import (
    EventListenerService, ParsedTrade
)
from app.services.blockchain.trade_queue import TradeQueueService


@pytest.fixture
def sample_trade():
    """Create sample ParsedTrade for testing"""
    return ParsedTrade(
        tx_hash="0xabcdef1234567890",
        block_number=50000000,
        block_timestamp=1700000000,
        log_index=5,
        trader_address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
        market_id="0x123456",
        market_name="Will Bitcoin reach $100k?",
        side="BUY",
        outcome="YES",
        quantity=Decimal("10.5"),
        price=Decimal("0.55"),
        total_value=Decimal("577.50"),
        fees=Decimal("0.50"),
        gas_used=150000,
        gas_price=50000000000
    )


@pytest.fixture
def mock_log():
    """Create mock blockchain log"""
    return {
        'transactionHash': Mock(hex=lambda: '0xabcdef1234567890'),
        'blockNumber': 50000000,
        'logIndex': 5,
        'address': '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E',
        'topics': [
            Mock(hex=lambda: EVENT_SIGNATURES['OrderFilled']),
            Mock(hex=lambda: '0x' + '0' * 64),  # orderHash
            Mock(hex=lambda: '0x' + '0' * 64),  # maker
        ],
        'data': '0x' + '0' * 256
    }


class TestParsedTrade:
    """Test ParsedTrade dataclass"""
    
    def test_to_dict(self, sample_trade):
        """Test serialization to dict"""
        data = sample_trade.to_dict()
        
        assert data['tx_hash'] == '0xabcdef1234567890'
        assert data['trader_address'] == '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1'
        assert isinstance(data['quantity'], str)  # Decimal converted to string
        assert data['quantity'] == '10.5'
    
    def test_validation_initialization(self, sample_trade):
        """Test validation errors initialization"""
        assert sample_trade.validation_errors == []
        assert sample_trade.is_valid is True


class TestEventListenerService:
    """Test EventListenerService"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test service initialization"""
        listener = EventListenerService()
        
        assert listener.is_running is False
        assert listener.latest_block == 0
        assert len(listener._trade_callbacks) == 0
    
    @pytest.mark.asyncio
    async def test_callback_registration(self):
        """Test trade callback registration"""
        listener = EventListenerService()
        
        async def callback(trade):
            pass
        
        listener.on_trade_detected(callback)
        
        assert len(listener._trade_callbacks) == 1
        assert listener._trade_callbacks[0] == callback
    
    @pytest.mark.asyncio
    async def test_event_deduplication(self):
        """Test that duplicate events are filtered"""
        listener = EventListenerService()
        
        event_id = "0xabc123:5"
        listener._processed_events.add(event_id)
        
        # Mock event with same ID
        mock_log = Mock()
        mock_log.__getitem__ = Mock(side_effect=lambda k: {
            'transactionHash': Mock(hex=lambda: '0xabc123'),
            'logIndex': 5
        }[k])
        
        await listener._process_event(mock_log)
        
        # Should increment duplicates counter
        assert listener.total_duplicates_filtered > 0
    
    def test_validate_trade(self):
        """Test trade validation"""
        listener = EventListenerService()
        
        # Valid trade
        trade = ParsedTrade(
            tx_hash="0xabc",
            block_number=100,
            block_timestamp=1000,
            log_index=0,
            trader_address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            market_id="0x123",
            side="BUY",
            outcome="YES",
            quantity=Decimal("10"),
            price=Decimal("0.5"),
            total_value=Decimal("5")
        )
        
        assert listener._validate_trade(trade) is True
        assert len(trade.validation_errors) == 0
    
    def test_validate_trade_invalid_price(self):
        """Test validation catches invalid price"""
        listener = EventListenerService()
        
        trade = ParsedTrade(
            tx_hash="0xabc",
            block_number=100,
            block_timestamp=1000,
            log_index=0,
            trader_address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1",
            market_id="0x123",
            side="BUY",
            outcome="YES",
            quantity=Decimal("10"),
            price=Decimal("1.5"),  # Invalid: > 1
            total_value=Decimal("5")
        )
        
        assert listener._validate_trade(trade) is False
        assert len(trade.validation_errors) > 0
        assert any('price' in err.lower() for err in trade.validation_errors)
    
    def test_validate_trade_missing_fields(self):
        """Test validation catches missing fields"""
        listener = EventListenerService()
        
        trade = ParsedTrade(
            tx_hash="",  # Missing
            block_number=100,
            block_timestamp=1000,
            log_index=0,
            trader_address="",  # Missing
            market_id="0x123",
            side="BUY",
            outcome="YES",
            quantity=Decimal("10"),
            price=Decimal("0.5"),
            total_value=Decimal("5")
        )
        
        assert listener._validate_trade(trade) is False
        assert "Missing tx_hash" in trade.validation_errors
        assert "Missing trader_address" in trade.validation_errors


@pytest.mark.asyncio
class TestTradeQueueService:
    """Test TradeQueueService"""
    
    async def test_initialization(self):
        """Test queue service initialization"""
        queue = TradeQueueService()
        
        assert queue.redis_client is None
        assert queue.total_pushed == 0
    
    async def test_push_and_consume_trade(self, sample_trade):
        """Test pushing and consuming trades"""
        queue = TradeQueueService()
        
        # Mock Redis client
        mock_redis = AsyncMock()
        mock_redis.rpush = AsyncMock()
        mock_redis.llen = AsyncMock(return_value=1)
        queue.redis_client = mock_redis
        
        # Push trade
        success = await queue.push_trade(sample_trade)
        
        assert success is True
        assert queue.total_pushed == 1
        mock_redis.rpush.assert_called_once()
    
    async def test_serialize_deserialize_trade(self, sample_trade):
        """Test trade serialization roundtrip"""
        queue = TradeQueueService()
        
        # Serialize
        trade_dict = sample_trade.to_dict()
        trade_dict['queued_at'] = datetime.utcnow().isoformat()
        trade_dict['retry_count'] = 0
        
        # Deserialize
        restored_trade = queue._deserialize_trade(trade_dict)
        
        assert restored_trade.tx_hash == sample_trade.tx_hash
        assert restored_trade.quantity == sample_trade.quantity
        assert isinstance(restored_trade.quantity, Decimal)
    
    async def test_mark_completed(self, sample_trade):
        """Test marking trade as completed"""
        queue = TradeQueueService()
        
        mock_redis = AsyncMock()
        mock_redis.hdel = AsyncMock()
        mock_redis.zadd = AsyncMock()
        queue.redis_client = mock_redis
        
        await queue.mark_completed(sample_trade.tx_hash)
        
        assert queue.total_completed == 1
        mock_redis.zadd.assert_called_once()
    
    async def test_mark_failed_with_retry(self, sample_trade):
        """Test marking trade as failed with retry"""
        queue = TradeQueueService()
        
        mock_redis = AsyncMock()
        mock_redis.hdel = AsyncMock()
        mock_redis.lpush = AsyncMock()
        queue.redis_client = mock_redis
        
        await queue.mark_failed(sample_trade, "Test error", retry=True)
        
        # Should push to retry queue
        mock_redis.lpush.assert_called()
        call_args = mock_redis.lpush.call_args
        assert call_args[0][0] == queue.RETRY_QUEUE
    
    async def test_mark_failed_dlq(self, sample_trade):
        """Test marking trade as failed (dead letter queue)"""
        queue = TradeQueueService()
        
        mock_redis = AsyncMock()
        mock_redis.hdel = AsyncMock()
        mock_redis.lpush = AsyncMock()
        queue.redis_client = mock_redis
        
        # Max retries exceeded
        await queue.mark_failed(sample_trade, "Final error", retry=False)
        
        # Should push to failed queue
        mock_redis.lpush.assert_called()
        call_args = mock_redis.lpush.call_args
        assert call_args[0][0] == queue.FAILED_QUEUE
        assert queue.total_failed == 1


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests"""
    
    async def test_full_pipeline_mock(self, sample_trade):
        """Test complete pipeline with mocks"""
        listener = EventListenerService()
        queue = TradeQueueService()
        
        # Mock queue connection
        queue.redis_client = AsyncMock()
        queue.redis_client.rpush = AsyncMock()
        queue.redis_client.llen = AsyncMock(return_value=1)
        
        # Register callback
        trades_received = []
        
        async def on_trade(trade):
            trades_received.append(trade)
            await queue.push_trade(trade)
        
        listener.on_trade_detected(on_trade)
        
        # Emit a trade
        await listener._emit_trade(sample_trade)
        
        # Verify trade was received and queued
        assert len(trades_received) == 1
        assert trades_received[0].tx_hash == sample_trade.tx_hash
        assert queue.total_pushed == 1
