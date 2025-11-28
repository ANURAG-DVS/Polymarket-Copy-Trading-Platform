"""
Copy Trading Services Package

Signal generation and trade execution.
"""

from app.services.copy_trading.signal_generation import (
    SignalGenerationService,
    get_signal_generation_service,
    CopyTradeSignal
)
from app.services.copy_trading.execution_worker import (
    TradeExecutionWorker,
    run_worker
)
from app.services.copy_trading.close_signals import (
    CloseSignalService,
    get_close_signal_service,
    CloseSignal,
    execute_close_signal,
    update_trade_on_close
)
from app.services.copy_trading.smart_execution import (
    SmartOrderExecutor,
    get_smart_executor,
    ExecutionPlan,
    ExecutionResult,
    OrderBookSnapshot
)

__all__ = [
    'SignalGenerationService',
    'get_signal_generation_service',
    'CopyTradeSignal',
    'TradeExecutionWorker',
    'run_worker',
    'CloseSignalService',
    'get_close_signal_service',
    'CloseSignal',
    'execute_close_signal',
    'update_trade_on_close',
    'SmartOrderExecutor',
    'get_smart_executor',
    'ExecutionPlan',
    'ExecutionResult',
    'OrderBookSnapshot',
]
