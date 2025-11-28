"""
Blockchain Services Package

Polygon blockchain monitoring for Polymarket trades.
"""

from app.services.blockchain.web3_provider import (
    Web3ProviderService,
    get_web3_provider_service,
    RPCEndpoint,
    RPCProviderConfig
)
from app.services.blockchain.contracts import (
    POLYMARKET_CONTRACTS,
    EVENT_SIGNATURES,
    TradeEvent,
    get_contract_abi,
    get_contract_address
)
from app.services.blockchain.block_monitor import (
    BlockMonitorService,
    get_block_monitor_service,
    BlockMonitorConfig
)
from app.services.blockchain.event_listener import (
    EventListenerService,
    get_event_listener_service,
    ParsedTrade
)
from app.services.blockchain.trade_queue import (
    TradeQueueService,
    get_trade_queue_service
)
from app.services.blockchain.pipeline import (
    setup_trade_pipeline,
    get_pipeline_status
)

__all__ = [
    # Web3 Provider
    'Web3ProviderService',
    'get_web3_provider_service',
    'RPCEndpoint',
    'RPCProviderConfig',
    
    # Contracts
    'POLYMARKET_CONTRACTS',
    'EVENT_SIGNATURES',
    'TradeEvent',
    'get_contract_abi',
    'get_contract_address',
    
    # Block Monitor
    'BlockMonitorService',
    'get_block_monitor_service',
    'BlockMonitorConfig',
    
    # Event Listener
    'EventListenerService',
    'get_event_listener_service',
    'ParsedTrade',
    
    # Trade Queue
    'TradeQueueService',
    'get_trade_queue_service',
    
    # Pipeline
    'setup_trade_pipeline',
    'get_pipeline_status',
]
