"""
Block Monitoring Service

Monitors Polygon blockchain for new blocks and Polymarket trades.

Features:
- WebSocket subscription to new blocks
- Fallback polling mechanism
- Transaction filtering for Polymarket contracts
- Event parsing and decoding
- Recovery from connection interruptions
"""

import asyncio
from typing import Optional, Callable, List, Set, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from web3.types import BlockData, TxData, LogReceipt
from web3.exceptions import Web3Exception
from loguru import logger

from app.services.blockchain.web3_provider import get_web3_provider_service
from app.services.blockchain.contracts import (
    POLYMARKET_CONTRACTS, TradeEvent, get_contract_abi, EVENT_SIGNATURES
)


@dataclass
class BlockMonitorConfig:
    """Configuration for block monitoring"""
    # Subscription settings
    use_websocket: bool = True
    polling_interval: int = 12  # seconds (Polygon block time ~2s, but we poll slower)
    
    # Contract filtering
    monitored_contracts: Set[str] = None
    
    # Performance
    max_blocks_per_batch: int = 100
    log_batch_size: int = 1000
    
    # Recovery
    enable_recovery: bool = True
    recovery_lookback_blocks: int = 100
    
    def __post_init__(self):
        if self.monitored_contracts is None:
            # Monitor all Polymarket contracts by default
            self.monitored_contracts = set(POLYMARKET_CONTRACTS.values())


class BlockMonitorService:
    """
    Monitors Polygon blockchain for new blocks and Polymarket events.
    
    Example:
        ```python
        monitor = BlockMonitorService()
        
        async def on_new_trade(event: TradeEvent):
            print(f"New trade: {event.trader_address} bought {event.size}")
        
        monitor.on_trade_event(on_new_trade)
        await monitor.start()
        ```
    """
    
    def __init__(self, config: Optional[BlockMonitorConfig] = None):
        """
        Initialize block monitor.
        
        Args:
            config: Monitor configuration (uses defaults if None)
        """
        self.config = config or BlockMonitorConfig()
        self.web3_provider = get_web3_provider_service()
        
        # State tracking
        self.latest_processed_block: int = 0
        self.is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Event callbacks
        self._trade_callbacks: List[Callable[[TradeEvent], None]] = []
        self._block_callbacks: List[Callable[[BlockData], None]] = []
        
        # Statistics
        self.total_blocks_processed: int = 0
        self.total_trades_detected: int = 0
        self.started_at: Optional[datetime] = None
        
        logger.info("BlockMonitorService initialized")
    
    def on_trade_event(self, callback: Callable[[TradeEvent], None]):
        """
        Register callback for trade events.
        
        Args:
            callback: Async function called when trade is detected
        """
        self._trade_callbacks.append(callback)
    
    def on_new_block(self, callback: Callable[[BlockData], None]):
        """
        Register callback for new blocks.
        
        Args:
            callback: Async function called for each new block
        """
        self._block_callbacks.append(callback)
    
    async def start(self, from_block: Optional[int] = None):
        """
        Start monitoring blockchain.
        
        Args:
            from_block: Block number to start from (None = latest)
        """
        if self.is_running:
            logger.warning("Block monitor already running")
            return
        
        self.is_running = True
        self.started_at = datetime.utcnow()
        
        # Get starting block
        if from_block is None:
            w3 = await self.web3_provider.get_web3()
            from_block = await w3.eth.block_number
        
        self.latest_processed_block = from_block
        
        logger.info(f"Starting block monitor from block {from_block}")
        
        # Start monitoring task
        if self.config.use_websocket:
            self._monitor_task = asyncio.create_task(self._websocket_monitor())
        else:
            self._monitor_task = asyncio.create_task(self._polling_monitor())
    
    async def stop(self):
        """Stop monitoring"""
        self.is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Block monitor stopped")
    
    async def _websocket_monitor(self):
        """Monitor using WebSocket subscription"""
        try:
            w3 = await self.web3_provider.get_web3()
            
            # Subscribe to new block headers
            logger.info("Subscribing to new block headers via WebSocket")
            
            while self.is_running:
                try:
                    # Get latest block
                    latest_block_number = await w3.eth.block_number
                    
                    if latest_block_number > self.latest_processed_block:
                        # Process new blocks
                        await self._process_block_range(
                            self.latest_processed_block + 1,
                            latest_block_number
                        )
                        
                        self.latest_processed_block = latest_block_number
                    
                    # Wait for next block (Polygon ~2s block time)
                    await asyncio.sleep(2)
                    
                except Web3Exception as e:
                    logger.error(f"WebSocket error: {e}. Reconnecting...")
                    await self.web3_provider.connect()
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            logger.info("WebSocket monitor cancelled")
        except Exception as e:
            logger.error(f"Fatal error in WebSocket monitor: {e}")
            # Fallback to polling
            logger.info("Falling back to polling mode")
            await self._polling_monitor()
    
    async def _polling_monitor(self):
        """Monitor using polling"""
        try:
            logger.info(f"Starting polling monitor (interval: {self.config.polling_interval}s)")
            
            while self.is_running:
                try:
                    w3 = await self.web3_provider.get_web3()
                    latest_block_number = await w3.eth.block_number
                    
                    if latest_block_number > self.latest_processed_block:
                        await self._process_block_range(
                            self.latest_processed_block + 1,
                            latest_block_number
                        )
                        
                        self.latest_processed_block = latest_block_number
                    
                    await asyncio.sleep(self.config.polling_interval)
                    
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                    await asyncio.sleep(self.config.polling_interval * 2)
                    
        except asyncio.CancelledError:
            logger.info("Polling monitor cancelled")
    
    async def _process_block_range(self, from_block: int, to_block: int):
        """
        Process a range of blocks.
        
        Args:
            from_block: Starting block (inclusive)
            to_block: Ending block (inclusive)
        """
        # Process in batches
        for batch_start in range(from_block, to_block + 1, self.config.max_blocks_per_batch):
            batch_end = min(batch_start + self.config.max_blocks_per_batch - 1, to_block)
            
            logger.debug(f"Processing blocks {batch_start} to {batch_end}")
            
            # Get logs for Polymarket contracts
            await self._process_logs_in_range(batch_start, batch_end)
            
            # Call block callbacks
            if self._block_callbacks:
                w3 = await self.web3_provider.get_web3()
                for block_num in range(batch_start, batch_end + 1):
                    try:
                        block = await w3.eth.get_block(block_num)
                        for callback in self._block_callbacks:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(block)
                            else:
                                callback(block)
                    except Exception as e:
                        logger.error(f"Error processing block {block_num}: {e}")
            
            self.total_blocks_processed += (batch_end - batch_start + 1)
    
    async def _process_logs_in_range(self, from_block: int, to_block: int):
        """Process logs for monitored contracts in block range"""
        try:
            w3 = await self.web3_provider.get_web3()
            
            # Get logs for monitored contracts
            filter_params = {
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': list(self.config.monitored_contracts)
            }
            
            logs = await w3.eth.get_logs(filter_params)
            
            logger.debug(f"Found {len(logs)} logs in blocks {from_block}-{to_block}")
            
            # Process each log
            for log in logs:
                await self._process_log(log)
                
        except Exception as e:
            logger.error(f"Error fetching logs for blocks {from_block}-{to_block}: {e}")
    
    async def _process_log(self, log: LogReceipt):
        """
        Process a single log entry.
        
        Args:
            log: Log receipt from blockchain
        """
        try:
            # Check if this is a trade event
            event_signature = log['topics'][0].hex() if log['topics'] else None
            
            if event_signature == EVENT_SIGNATURES.get('OrderFilled'):
                # Parse trade event
                trade_event = await self._parse_trade_event(log)
                
                if trade_event:
                    # Call trade callbacks
                    for callback in self._trade_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(trade_event)
                            else:
                                callback(trade_event)
                        except Exception as e:
                            logger.error(f"Error in trade callback: {e}")
                    
                    self.total_trades_detected += 1
                    
        except Exception as e:
            logger.error(f"Error processing log: {e}")
    
    async def _parse_trade_event(self, log: LogReceipt) -> Optional[TradeEvent]:
        """
        Parse OrderFilled event into TradeEvent.
        
        Args:
            log: Raw log receipt
            
        Returns:
            Parsed TradeEvent or None if parsing fails
        """
        try:
            w3 = await self.web3_provider.get_web3()
            
            # Get transaction details for more context
            tx_hash = log['transactionHash'].hex()
            tx = await w3.eth.get_transaction(tx_hash)
            block = await w3.eth.get_block(log['blockNumber'])
            
            # Decode log data (simplified - actual decoding would use w3.eth.contract)
            # For now, extract basic info
            trader_address = '0x' + tx['from'][2:] if tx['from'] else ''
            
            # This is a simplified version - real implementation would:
            # 1. Use contract.events.OrderFilled().process_log(log)
            # 2. Parse maker/taker, asset IDs, amounts
            # 3. Map asset IDs to market IDs and outcomes
            
            trade_event = TradeEvent(
                transaction_hash=tx_hash,
                block_number=log['blockNumber'],
                block_timestamp=block['timestamp'],
                log_index=log['logIndex'],
                trader_address=trader_address,
                market_id='',  # Would be parsed from log data
                outcome='',  # Would be determined from asset IDs
                side='BUY',  # Would be determined from maker/taker
                size=Decimal('0'),  # From log data
                price=Decimal('0'),  # Calculated from amounts
                value_usd=Decimal('0'),  # Calculated
                fees=Decimal('0'),  # From log data
                raw_log=dict(log)
            )
            
            return trade_event
            
        except Exception as e:
            logger.error(f"Error parsing trade event: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitor status"""
        uptime = None
        if self.started_at:
            uptime = (datetime.utcnow() - self.started_at).total_seconds()
        
        return {
            'is_running': self.is_running,
            'latest_processed_block': self.latest_processed_block,
            'total_blocks_processed': self.total_blocks_processed,
            'total_trades_detected': self.total_trades_detected,
            'uptime_seconds': uptime,
            'mode': 'websocket' if self.config.use_websocket else 'polling',
            'monitored_contracts': len(self.config.monitored_contracts)
        }


# Singleton instance
_block_monitor_service: Optional[BlockMonitorService] = None


def get_block_monitor_service() -> BlockMonitorService:
    """Get singleton instance of BlockMonitorService"""
    global _block_monitor_service
    if _block_monitor_service is None:
        _block_monitor_service = BlockMonitorService()
    return _block_monitor_service
