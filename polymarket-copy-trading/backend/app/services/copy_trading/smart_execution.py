"""
Smart Order Execution Service

Sophisticated order execution logic to minimize slippage and price impact.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass
from loguru import logger
import asyncio

from app.services.polymarket import get_polymarket_client


@dataclass
class OrderBookSnapshot:
    """Order book snapshot"""
    bids: List[tuple[Decimal, Decimal]]  # (price, quantity)
    asks: List[tuple[Decimal, Decimal]]  # (price, quantity)
    timestamp: datetime


@dataclass
class ExecutionPlan:
    """Smart execution plan"""
    order_type: str  # market, limit, split
    chunks: List[Dict[str, Any]]  # List of order chunks
    estimated_price: Decimal
    estimated_slippage_percent: Decimal
    warnings: List[str]


@dataclass
class ExecutionResult:
    """Execution result with analysis"""
    success: bool
    executed_price: Decimal
    requested_quantity: Decimal
    filled_quantity: Decimal
    slippage_percent: Decimal
    total_value: Decimal
    warnings: List[str]


class SmartOrderExecutor:
    """
    Intelligent order execution with slippage minimization.
    
    Features:
    - Pre-trade price analysis
    - Order splitting for large trades
    - Slippage protection
    - Market depth analysis
    """
    
    # Order size thresholds (USD)
    SMALL_ORDER_THRESHOLD = Decimal('100')
    LARGE_ORDER_THRESHOLD = Decimal('1000')
    
    # Execution parameters
    DEFAULT_MAX_SLIPPAGE_PERCENT = Decimal('5.0')
    CHUNK_DELAY_SECONDS = 30
    MAX_CHUNKS = 10
    
    def __init__(self):
        """Initialize smart executor"""
        logger.info("SmartOrderExecutor initialized")
    
    async def fetch_order_book(
        self,
        market_id: str,
        outcome: str
    ) -> OrderBookSnapshot:
        """
        Fetch current order book.
        
        Args:
            market_id: Market ID
            outcome: YES/NO
        
        Returns:
            OrderBookSnapshot
        """
        polymarket_client = get_polymarket_client()
        
        # Fetch order book from Polymarket
        # In production, would call actual API
        order_book = await polymarket_client.get_order_book(market_id, outcome)
        
        # Parse bids and asks
        bids = [
            (Decimal(str(level['price'])), Decimal(str(level['quantity'])))
            for level in order_book.get('bids', [])
        ]
        
        asks = [
            (Decimal(str(level['price'])), Decimal(str(level['quantity'])))
            for level in order_book.get('asks', [])
        ]
        
        return OrderBookSnapshot(
            bids=bids,
            asks=asks,
            timestamp=datetime.utcnow()
        )
    
    async def estimate_execution_price(
        self,
        order_book: OrderBookSnapshot,
        quantity: Decimal,
        side: str
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate estimated execution price based on order book.
        
        Uses volume-weighted average price (VWAP) from order book.
        
        Args:
            order_book: Order book snapshot
            quantity: Quantity to execute
            side: 'buy' or 'sell'
        
        Returns:
            (estimated_price, estimated_slippage_percent)
        """
        # Select appropriate book side
        levels = order_book.asks if side == 'buy' else order_book.bids
        
        if not levels:
            # No liquidity
            return Decimal('0'), Decimal('100')
        
        # Get best price (first level)
        best_price = levels[0][0]
        
        # Calculate VWAP
        remaining_qty = quantity
        total_cost = Decimal('0')
        filled_qty = Decimal('0')
        
        for price, available_qty in levels:
            if remaining_qty <= 0:
                break
            
            fill_qty = min(remaining_qty, available_qty)
            total_cost += price * fill_qty
            filled_qty += fill_qty
            remaining_qty -= fill_qty
        
        if filled_qty == 0:
            # Insufficient liquidity
            return best_price, Decimal('100')
        
        # Calculate weighted average price
        avg_price = total_cost / filled_qty
        
        # Calculate slippage percentage
        slippage = abs((avg_price - best_price) / best_price) * 100
        
        logger.info(
            f"Estimated execution: qty={quantity}, "
            f"best_price={best_price}, "
            f"avg_price={avg_price}, "
            f"slippage={slippage}%"
        )
        
        return avg_price, slippage
    
    async def check_market_depth(
        self,
        order_book: OrderBookSnapshot,
        quantity: Decimal,
        side: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if market has sufficient depth for order.
        
        Args:
            order_book: Order book snapshot
            quantity: Order quantity
            side: 'buy' or 'sell'
        
        Returns:
            (has_liquidity, warning_message)
        """
        levels = order_book.asks if side == 'buy' else order_book.bids
        
        # Calculate total available quantity
        total_available = sum(qty for _, qty in levels)
        
        if total_available < quantity:
            return False, (
                f"Insufficient liquidity: "
                f"available={total_available}, "
                f"requested={quantity}. "
                f"Consider reducing copy percentage."
            )
        
        # Check if order would consume >50% of book
        if total_available < quantity * 2:
            return True, (
                f"Warning: Large order relative to market depth. "
                f"May experience significant price impact."
            )
        
        return True, None
    
    async def create_execution_plan(
        self,
        market_id: str,
        outcome: str,
        quantity: Decimal,
        amount_usd: Decimal,
        side: str,
        max_slippage_percent: Optional[Decimal] = None
    ) -> ExecutionPlan:
        """
        Create smart execution plan based on order size and market conditions.
        
        Args:
            market_id: Market ID
            outcome: YES/NO
            quantity: Quantity to trade
            amount_usd: Trade amount in USD
            side: 'buy' or 'sell'
            max_slippage_percent: Maximum acceptable slippage
        
        Returns:
            ExecutionPlan
        """
        if max_slippage_percent is None:
            max_slippage_percent = self.DEFAULT_MAX_SLIPPAGE_PERCENT
        
        warnings = []
        
        # Fetch order book
        order_book = await self.fetch_order_book(market_id, outcome)
        
        # Estimate execution price
        estimated_price, estimated_slippage = await self.estimate_execution_price(
            order_book,
            quantity,
            side
        )
        
        # Check market depth
        has_liquidity, depth_warning = await self.check_market_depth(
            order_book,
            quantity,
            side
        )
        
        if depth_warning:
            warnings.append(depth_warning)
        
        if not has_liquidity:
            # Insufficient liquidity - split aggressively
            num_chunks = self.MAX_CHUNKS
            order_type = "split"
        elif estimated_slippage > max_slippage_percent:
            # High slippage - split order
            warnings.append(
                f"High slippage detected ({estimated_slippage:.2f}%). "
                f"Splitting order to minimize impact."
            )
            num_chunks = min(5, int(amount_usd / self.SMALL_ORDER_THRESHOLD) + 1)
            order_type = "split"
        elif amount_usd < self.SMALL_ORDER_THRESHOLD:
            # Small order - use market order
            order_type = "market"
            num_chunks = 1
        elif amount_usd < self.LARGE_ORDER_THRESHOLD:
            # Medium order - use limit order
            order_type = "limit"
            num_chunks = 1
        else:
            # Large order - split
            order_type = "split"
            num_chunks = min(self.MAX_CHUNKS, int(amount_usd / Decimal('200')))
        
        # Create chunks
        chunk_quantity = quantity / num_chunks
        chunks = []
        
        for i in range(num_chunks):
            chunks.append({
                "chunk_number": i + 1,
                "quantity": float(chunk_quantity),
                "delay_seconds": i * self.CHUNK_DELAY_SECONDS if i > 0 else 0
            })
        
        logger.info(
            f"Execution plan created: "
            f"type={order_type}, "
            f"chunks={num_chunks}, "
            f"estimated_slippage={estimated_slippage}%"
        )
        
        return ExecutionPlan(
            order_type=order_type,
            chunks=chunks,
            estimated_price=estimated_price,
            estimated_slippage_percent=estimated_slippage,
            warnings=warnings
        )
    
    async def execute_with_plan(
        self,
        plan: ExecutionPlan,
        market_id: str,
        outcome: str,
        side: str,
        api_credentials: dict
    ) -> ExecutionResult:
        """
        Execute trade according to plan.
        
        Args:
            plan: Execution plan
            market_id: Market ID
            outcome: YES/NO
            side: 'buy' or 'sell'
            api_credentials: User's API credentials
        
        Returns:
            ExecutionResult
        """
        polymarket_client = get_polymarket_client()
        # polymarket_client.set_credentials(api_credentials)
        
        total_filled = Decimal('0')
        total_cost = Decimal('0')
        warnings = list(plan.warnings)
        
        for chunk in plan.chunks:
            # Delay between chunks
            if chunk['delay_seconds'] > 0:
                logger.info(f"Waiting {chunk['delay_seconds']}s before next chunk...")
                await asyncio.sleep(chunk['delay_seconds'])
            
            chunk_qty = Decimal(str(chunk['quantity']))
            
            try:
                # Fetch fresh price for this chunk
                current_order_book = await self.fetch_order_book(market_id, outcome)
                current_price, current_slippage = await self.estimate_execution_price(
                    current_order_book,
                    chunk_qty,
                    side
                )
                
                # Check if slippage acceptable
                if current_slippage > plan.estimated_slippage_percent * Decimal('1.5'):
                    warning = (
                        f"Chunk {chunk['chunk_number']}: "
                        f"Slippage increased to {current_slippage}%. "
                        f"Adjusting limit price."
                    )
                    warnings.append(warning)
                    logger.warning(warning)
                
                # Execute chunk
                if plan.order_type == "market":
                    # Market order
                    response = await polymarket_client.place_market_order(
                        market_id=market_id,
                        outcome=outcome,
                        quantity=float(chunk_qty),
                        side=side
                    )
                else:
                    # Limit order with current price
                    slippage_factor = Decimal('0.01')  # 1% slippage tolerance
                    if side == 'buy':
                        limit_price = current_price * (1 + slippage_factor)
                    else:
                        limit_price = current_price * (1 - slippage_factor)
                    
                    response = await polymarket_client.place_limit_order(
                        market_id=market_id,
                        outcome=outcome,
                        quantity=float(chunk_qty),
                        price=float(limit_price),
                        side=side
                    )
                
                # Parse response
                filled_qty = Decimal(str(response.get('filled_quantity', chunk_qty)))
                filled_price = Decimal(str(response.get('average_price', current_price)))
                
                total_filled += filled_qty
                total_cost += filled_qty * filled_price
                
                logger.info(
                    f"Chunk {chunk['chunk_number']} executed: "
                    f"filled={filled_qty}, price={filled_price}"
                )
                
            except Exception as e:
                error_msg = f"Chunk {chunk['chunk_number']} failed: {str(e)}"
                warnings.append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        # Calculate results
        if total_filled > 0:
            avg_executed_price = total_cost / total_filled
            slippage = abs((avg_executed_price - plan.estimated_price) / plan.estimated_price) * 100
            
            return ExecutionResult(
                success=True,
                executed_price=avg_executed_price,
                requested_quantity=sum(Decimal(str(c['quantity'])) for c in plan.chunks),
                filled_quantity=total_filled,
                slippage_percent=slippage,
                total_value=total_cost,
                warnings=warnings
            )
        else:
            return ExecutionResult(
                success=False,
                executed_price=Decimal('0'),
                requested_quantity=sum(Decimal(str(c['quantity'])) for c in plan.chunks),
                filled_quantity=Decimal('0'),
                slippage_percent=Decimal('100'),
                total_value=Decimal('0'),
                warnings=warnings + ["No fills executed"]
            )
    
    async def log_execution_analytics(
        self,
        result: ExecutionResult,
        plan: ExecutionPlan
    ):
        """
        Log execution analytics for optimization.
        
        Args:
            result: Execution result
            plan: Original execution plan
        """
        analytics = {
            "timestamp": datetime.utcnow().isoformat(),
            "order_type": plan.order_type,
            "num_chunks": len(plan.chunks),
            "estimated_price": float(plan.estimated_price),
            "executed_price": float(result.executed_price),
            "estimated_slippage": float(plan.estimated_slippage_percent),
            "actual_slippage": float(result.slippage_percent),
            "fill_rate": float(result.filled_quantity / result.requested_quantity * 100),
            "warnings_count": len(result.warnings)
        }
        
        # TODO: Store in analytics database
        logger.info(f"Execution analytics: {analytics}")


# Singleton instance
_smart_executor: Optional[SmartOrderExecutor] = None


def get_smart_executor() -> SmartOrderExecutor:
    """Get singleton instance"""
    global _smart_executor
    if _smart_executor is None:
        _smart_executor = SmartOrderExecutor()
    return _smart_executor
