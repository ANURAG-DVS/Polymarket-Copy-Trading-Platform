"""
Real-Time Event Listener for Polymarket Trades

Detects and processes Polymarket trade events from the blockchain in real-time.

Features:
- Listen to OrderFilled and related events
- Parse transaction data into standardized format
- Handle blockchain reorganizations
- Deduplicate events
- Queue parsed trades for processing
"""

import asyncio
from typing import Optional, Set, Dict, Any, Callable, List
from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import datetime
from web3.types import LogReceipt, TxReceipt
from eth_utils import to_checksum_address
from loguru import logger

from app.services.blockchain.web3_provider import get_web3_provider_service
from app.services.blockchain.contracts import (
    POLYMARKET_CONTRACTS, get_contract_abi, EVENT_SIGNATURES
)


@dataclass
class ParsedTrade:
    """Standardized trade object"""
    # Transaction info
    tx_hash: str
    block_number: int
    block_timestamp: int
    log_index: int
    
    # Trader info
    trader_address: str  # Checksummed address
    
    # Market info
    market_id: str
    market_name: Optional[str] = None
    
    # Trade details
    side: str  # "BUY" or "SELL"
    outcome: str  # "YES" or "NO"
    quantity: Decimal
    price: Decimal
    total_value: Decimal
    
    # Fees
    fees: Decimal = Decimal('0')
    gas_used: int = 0
    gas_price: int = 0
    
    # Metadata
    is_maker: bool = False
    order_id: Optional[str] = None
    
    # Status
    is_valid: bool = True
    validation_errors: List[str] = None
    
    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert Decimal to string for JSON serialization
        data['quantity'] = str(self.quantity)
        data['price'] = str(self.price)
        data['total_value'] = str(self.total_value)
        data['fees'] = str(self.fees)
        return data


class EventListenerService:
    """
    Real-time listener for Polymarket trade events.
    
    Example:
        ```python
        listener = EventListenerService()
        
        async def on_trade(trade: ParsedTrade):
            print(f"New trade: {trade.trader_address} - {trade.side}")
            # Push to processing queue
        
        listener.on_trade_detected(on_trade)
        await listener.start()
        ```
    """
    
    def __init__(self):
        """Initialize event listener"""
        self.web3_provider = get_web3_provider_service()
        
        # Event tracking
        self._processed_events: Set[str] = set()  # event_id = tx_hash:log_index
        self._reorg_buffer: Dict[int, List[ParsedTrade]] = {}  # block_number -> trades
        
        # Callbacks
        self._trade_callbacks: List[Callable[[ParsedTrade], None]] = []
        
        # State
        self.is_running: bool = False
        self._listener_task: Optional[asyncio.Task] = None
        self.latest_block: int = 0
        
        # Statistics
        self.total_events_processed: int = 0
        self.total_trades_parsed: int = 0
        self.total_duplicates_filtered: int = 0
        self.total_invalid_trades: int = 0
        
        # Configuration
        self.reorg_confirmation_blocks: int = 12  # Wait 12 blocks before finalizing
        self.max_buffer_size: int = 1000
        
        logger.info("EventListenerService initialized")
    
    def on_trade_detected(self, callback: Callable[[ParsedTrade], None]):
        """
        Register callback for parsed trades.
        
        Args:
            callback: Async function called with ParsedTrade
        """
        self._trade_callbacks.append(callback)
    
    async def start(self, from_block: Optional[int] = None):
        """
        Start listening to events.
        
        Args:
            from_block: Block to start from (None = latest)
        """
        if self.is_running:
            logger.warning("Event listener already running")
            return
        
        self.is_running = True
        
        # Get starting block
        if from_block is None:
            w3 = await self.web3_provider.get_web3()
            from_block = await w3.eth.block_number
        
        self.latest_block = from_block
        
        logger.info(f"Starting event listener from block {from_block}")
        
        # Start listening task
        self._listener_task = asyncio.create_task(self._listen_loop())
    
    async def stop(self):
        """Stop listening"""
        self.is_running = False
        
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Event listener stopped")
    
    async def _listen_loop(self):
        """Main listening loop"""
        try:
            while self.is_running:
                try:
                    w3 = await self.web3_provider.get_web3()
                    current_block = await w3.eth.block_number
                    
                    if current_block > self.latest_block:
                        # Process new blocks
                        await self._process_new_blocks(
                            self.latest_block + 1,
                            current_block
                        )
                        
                        self.latest_block = current_block
                        
                        # Clean up old reorg buffer
                        await self._cleanup_reorg_buffer(current_block)
                    
                    # Wait for next block
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error in listen loop: {e}")
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            logger.info("Listen loop cancelled")
    
    async def _process_new_blocks(self, from_block: int, to_block: int):
        """
        Process new blocks for events.
        
        Args:
            from_block: Starting block
            to_block: Ending block
        """
        logger.debug(f"Processing blocks {from_block} to {to_block}")
        
        try:
            w3 = await self.web3_provider.get_web3()
            
            # Get logs for Polymarket contracts
            filter_params = {
                'fromBlock': from_block,
                'toBlock': to_block,
                'address': [
                    POLYMARKET_CONTRACTS['CTF_EXCHANGE'],
                    POLYMARKET_CONTRACTS['NEG_RISK_CTF_EXCHANGE']
                ],
                'topics': [
                    # OrderFilled event signature
                    EVENT_SIGNATURES['OrderFilled']
                ]
            }
            
            logs = await w3.eth.get_logs(filter_params)
            
            logger.info(f"Found {len(logs)} OrderFilled events in blocks {from_block}-{to_block}")
            
            # Process each log
            for log in logs:
                await self._process_event(log)
                
        except Exception as e:
            logger.error(f"Error processing blocks {from_block}-{to_block}: {e}")
    
    async def _process_event(self, log: LogReceipt):
        """
        Process a single event log.
        
        Args:
            log: Event log from blockchain
        """
        try:
            # Create event ID for deduplication
            event_id = f"{log['transactionHash'].hex()}:{log['logIndex']}"
            
            # Check if already processed
            if event_id in self._processed_events:
                self.total_duplicates_filtered += 1
                logger.debug(f"Skipping duplicate event: {event_id}")
                return
            
            self.total_events_processed += 1
            
            # Parse the event
            trade = await self._parse_event(log)
            
            if not trade:
                logger.warning(f"Failed to parse event: {event_id}")
                return
            
            # Validate trade
            if not self._validate_trade(trade):
                self.total_invalid_trades += 1
                logger.warning(f"Invalid trade: {event_id} - {trade.validation_errors}")
                return
            
            self.total_trades_parsed += 1
            
            # Add to reorg buffer (wait for confirmations)
            if trade.block_number not in self._reorg_buffer:
                self._reorg_buffer[trade.block_number] = []
            self._reorg_buffer[trade.block_number].append(trade)
            
            # Mark as processed
            self._processed_events.add(event_id)
            
            # If block is confirmed (past reorg risk), emit trade
            if self.latest_block - trade.block_number >= self.reorg_confirmation_blocks:
                await self._emit_trade(trade)
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
    async def _parse_event(self, log: LogReceipt) -> Optional[ParsedTrade]:
        """
        Parse OrderFilled event into ParsedTrade.
        
        Args:
            log: Event log
            
        Returns:
            Parsed trade or None if parsing fails
        """
        try:
            w3 = await self.web3_provider.get_web3()
            
            # Get transaction and receipt
            tx_hash = log['transactionHash'].hex()
            tx = await w3.eth.get_transaction(tx_hash)
            receipt = await w3.eth.get_transaction_receipt(tx_hash)
            block = await w3.eth.get_block(log['blockNumber'])
            
            # Verify transaction success
            if receipt['status'] != 1:
                logger.debug(f"Transaction {tx_hash} failed, skipping")
                return None
            
            # Create contract instance for event decoding
            contract_address = to_checksum_address(log['address'])
            contract = w3.eth.contract(
                address=contract_address,
                abi=get_contract_abi('CTF_EXCHANGE')
            )
            
            # Decode event
            try:
                event_data = contract.events.OrderFilled().process_log(log)
            except Exception as e:
                logger.error(f"Failed to decode event: {e}")
                # Fallback: manual parsing
                event_data = self._manual_parse_event(log)
            
            # Extract trade details
            args = event_data.get('args', {})
            
            # Determine trader (use 'from' address as trader for now)
            trader_address = to_checksum_address(tx['from'])
            
            # Extract amounts (these are in token units, usually 1e6 for USDC)
            maker_amount = Decimal(str(args.get('makerAmountFilled', 0))) / Decimal('1e6')
            taker_amount = Decimal(str(args.get('takerAmountFilled', 0))) / Decimal('1e6')
            
            # Calculate price and determine side
            # In Polymarket, price is probability (0-1)
            # Side is determined by whether user is buying YES or NO tokens
            if maker_amount > 0 and taker_amount > 0:
                price = taker_amount / maker_amount if maker_amount > 0 else Decimal('0')
            else:
                price = Decimal('0')
            
            # Determine side (simplified - real implementation needs more context)
            side = "BUY"  # This would be determined from asset IDs
            outcome = "YES"  # This would be mapped from asset IDs
            
            # Get market ID from asset IDs
            maker_asset_id = args.get('makerAssetId', 0)
            market_id = f"0x{maker_asset_id:064x}"  # Convert to hex
            
            # Fees
            fee = Decimal(str(args.get('fee', 0))) / Decimal('1e6')
            
            # Create ParsedTrade
            trade = ParsedTrade(
                tx_hash=tx_hash,
                block_number=log['blockNumber'],
                block_timestamp=block['timestamp'],
                log_index=log['logIndex'],
                trader_address=trader_address,
                market_id=market_id,
                market_name=None,  # Would be fetched from Polymarket API
                side=side,
                outcome=outcome,
                quantity=maker_amount,
                price=price,
                total_value=taker_amount,
                fees=fee,
                gas_used=receipt['gasUsed'],
                gas_price=tx['gasPrice'],
                is_maker=False,  # Would be determined from event data
                order_id=args.get('orderHash', '').hex() if 'orderHash' in args else None
            )
            
            return trade
            
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    def _manual_parse_event(self, log: LogReceipt) -> Dict[str, Any]:
        """Manually parse event data if contract decoding fails"""
        # Fallback parsing using raw log data
        # This is a simplified version
        return {
            'args': {
                'orderHash': log['topics'][1] if len(log['topics']) > 1 else None,
                'maker': log['topics'][2] if len(log['topics']) > 2 else None,
                'makerAmountFilled': 0,
                'takerAmountFilled': 0,
                'fee': 0
            }
        }
    
    def _validate_trade(self, trade: ParsedTrade) -> bool:
        """
        Validate parsed trade data.
        
        Args:
            trade: Parsed trade to validate
            
        Returns:
            True if valid, False otherwise
        """
        errors = []
        
        # Validate required fields
        if not trade.tx_hash:
            errors.append("Missing tx_hash")
        
        if not trade.trader_address:
            errors.append("Missing trader_address")
        else:
            # Validate address checksum
            try:
                to_checksum_address(trade.trader_address)
            except Exception:
                errors.append("Invalid trader_address checksum")
        
        if not trade.market_id:
            errors.append("Missing market_id")
        
        if trade.side not in ['BUY', 'SELL']:
            errors.append(f"Invalid side: {trade.side}")
        
        if trade.outcome not in ['YES', 'NO']:
            errors.append(f"Invalid outcome: {trade.outcome}")
        
        # Validate amounts
        if trade.quantity <= 0:
            errors.append(f"Invalid quantity: {trade.quantity}")
        
        if trade.price < 0 or trade.price > 1:
            errors.append(f"Invalid price: {trade.price} (must be 0-1)")
        
        if trade.total_value < 0:
            errors.append(f"Invalid total_value: {trade.total_value}")
        
        # Update trade with validation errors
        trade.validation_errors = errors
        trade.is_valid = len(errors) == 0
        
        return trade.is_valid
    
    async def _cleanup_reorg_buffer(self, current_block: int):
        """
        Clean up old blocks from reorg buffer and emit confirmed trades.
        
        Args:
            current_block: Current blockchain head
        """
        confirmed_blocks = []
        
        for block_num in list(self._reorg_buffer.keys()):
            # If block is past confirmation threshold, emit trades
            if current_block - block_num >= self.reorg_confirmation_blocks:
                trades = self._reorg_buffer[block_num]
                
                for trade in trades:
                    await self._emit_trade(trade)
                
                confirmed_blocks.append(block_num)
        
        # Remove confirmed blocks
        for block_num in confirmed_blocks:
            del self._reorg_buffer[block_num]
        
        # Limit buffer size
        if len(self._reorg_buffer) > self.max_buffer_size:
            logger.warning(f"Reorg buffer size {len(self._reorg_buffer)} exceeds limit")
            # Remove oldest blocks
            sorted_blocks = sorted(self._reorg_buffer.keys())
            for block_num in sorted_blocks[:len(sorted_blocks) - self.max_buffer_size]:
                del self._reorg_buffer[block_num]
    
    async def _emit_trade(self, trade: ParsedTrade):
        """
        Emit validated trade to callbacks.
        
        Args:
            trade: Confirmed and validated trade
        """
        logger.info(
            f"Trade confirmed: {trade.trader_address[:10]}... "
            f"{trade.side} {trade.quantity} @ {trade.price}"
        )
        
        # Call all registered callbacks
        for callback in self._trade_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trade)
                else:
                    callback(trade)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get listener status"""
        return {
            'is_running': self.is_running,
            'latest_block': self.latest_block,
            'total_events_processed': self.total_events_processed,
            'total_trades_parsed': self.total_trades_parsed,
            'total_duplicates_filtered': self.total_duplicates_filtered,
            'total_invalid_trades': self.total_invalid_trades,
            'buffered_blocks': len(self._reorg_buffer),
            'processed_events_count': len(self._processed_events)
        }


# Singleton instance
_event_listener_service: Optional[EventListenerService] = None


def get_event_listener_service() -> EventListenerService:
    """Get singleton instance of EventListenerService"""
    global _event_listener_service
    if _event_listener_service is None:
        _event_listener_service = EventListenerService()
    return _event_listener_service
