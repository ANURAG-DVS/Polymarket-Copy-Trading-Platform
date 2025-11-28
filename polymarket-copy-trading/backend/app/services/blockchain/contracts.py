"""
Polymarket Contract Interfaces

Smart contract addresses and ABIs for Polymarket on Polygon.

Polymarket uses the CLOB (Central Limit Order Book) system with:
- CTF Exchange contract for trading
- Conditional Tokens Framework (CTF) for outcome tokens
- Order book contracts for market making
"""

from dataclasses import dataclass
from typing import Dict, Any, List
from decimal import Decimal


# Polymarket Contract Addresses on Polygon
POLYMARKET_CONTRACTS = {
    # Main trading contract (CTF Exchange)
    'CTF_EXCHANGE': '0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E',
    
    # Conditional Tokens Framework
    'CTF': '0x4D97DCd97eC945f4​0Cf65F87097ACe5EA0476045',
    
    # Order Book proxy
    'ORDER_BOOK': '0xdFE02Eb6733538f8Ea35D585af8DE5958AD99E40',
    
    # Neg Risk CTF Exchange (for certain market types)
    'NEG_RISK_CTF_EXCHANGE': '0xC5d563A36AE78145C45a50134d48A1215220f80a',
}


# Event signatures for tracking
EVENT_SIGNATURES = {
    # Order placed event
    'OrderFilled': '0x52a2c9e52d3f2c8f7a75b3b0e0e3c1c2f7e3b8c5d8e2f3a4b5c6d7e8f9a0b1c2',
    
    # Position minted (outcome tokens created)
    'PositionSplit': '0x93c1f3e36ed71139f46f2f88b3f6f86ff0685c96a2a3b7c8aa7f3f6c9b9e3a23',
    
    # Position merged (tokens redeemed)
    'PositionMerged': '0xa1f4c8e3d2b5f6a7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1',
    
    # Transfer (ERC20/ERC1155)
    'Transfer': '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef',
    'TransferSingle': '0xc3d58168c5ae7397731d063d5bbffffffffffffffffffffffcd6d7e3c96d38e85',
    'TransferBatch': '0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e59​5b87c1e85ef9b94fc3f7',
}


@dataclass
class TradeEvent:
    """Parsed trade event from blockchain"""
    transaction_hash: str
    block_number: int
    block_timestamp: int
    log_index: int
    
    # Trade details
    trader_address: str
    market_id: str
    outcome: str  # "YES" or "NO"
    side: str  # "BUY" or "SELL"
    
    # Amounts
    size: Decimal
    price: Decimal
    value_usd: Decimal
    fees: Decimal
    
    # Raw data
    raw_log: Dict[str, Any]


# Simplified CTF Exchange ABI (key functions and events)
CTF_EXCHANGE_ABI = [
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
            {"indexed": True, "name": "maker", "type": "address"},
            {"indexed": False, "name": "taker", "type": "address"},
            {"indexed": False, "name": "makerAssetId", "type": "uint256"},
            {"indexed": False, "name": "takerAssetId", "type": "uint256"},
            {"indexed": False, "name": "makerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "takerAmountFilled", "type": "uint256"},
            {"indexed": False, "name": "fee", "type": "uint256"},
        ],
        "name": "OrderFilled",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "orderHash", "type": "bytes32"},
        ],
        "name": "OrderCancelled",
        "type": "event"
    },
    # Functions
    {
        "inputs": [],
        "name": "getOrderStatus",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
]


# Conditional Tokens Framework ABI
CTF_ABI = [
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "stakeholder", "type": "address"},
            {"indexed": False, "name": "collateralToken", "type": "address"},
            {"indexed": True, "name": "parentCollectionId", "type": "bytes32"},
            {"indexed": True, "name": "conditionId", "type": "bytes32"},
            {"indexed": False, "name": "partition", "type": "uint256[]"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "PositionSplit",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "stakeholder", "type": "address"},
            {"indexed": False, "name": "collateralToken", "type": "address"},
            {"indexed": True, "name": "parentCollectionId", "type": "bytes32"},
            {"indexed": True, "name": "conditionId", "type": "bytes32"},
            {"indexed": False, "name": "partition", "type": "uint256[]"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "PositionMerged",
        "type": "event"
    },
    # ERC1155 Transfer events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "id", "type": "uint256"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "TransferSingle",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "operator", "type": "address"},
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "ids", "type": "uint256[]"},
            {"indexed": False, "name": "values", "type": "uint256[]"},
        ],
        "name": "TransferBatch",
        "type": "event"
    },
]


def get_contract_abi(contract_name: str) -> List[Dict[str, Any]]:
    """
    Get ABI for a contract.
    
    Args:
        contract_name: Contract name (e.g., 'CTF_EXCHANGE', 'CTF')
        
    Returns:
        Contract ABI as list of function/event definitions
    """
    abis = {
        'CTF_EXCHANGE': CTF_EXCHANGE_ABI,
        'NEG_RISK_CTF_EXCHANGE': CTF_EXCHANGE_ABI,  # Same ABI
        'CTF': CTF_ABI,
    }
    
    return abis.get(contract_name, [])


def get_contract_address(contract_name: str) -> str:
    """
    Get deployed contract address.
    
    Args:
        contract_name: Contract name
        
    Returns:
        Contract address on Polygon
    """
    return POLYMARKET_CONTRACTS.get(contract_name, '')
