"""
GraphQL query templates for The Graph Protocol's Polymarket subgraph.

This module contains all GraphQL queries used to fetch trader data, positions,
and market information from the Polymarket subgraph. Queries are optimized for
performance and include proper filtering and pagination support.

Note: These queries assume the standard Polymarket subgraph schema. If the actual
schema differs, field names and structures may need adjustment.
"""

from typing import Dict, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import re


# ============================================================================
# GraphQL Query Templates
# ============================================================================

TOP_TRADERS_QUERY = """
query GetTopTraders($startTime: Int!, $limit: Int!) {
  users(
    first: $limit,
    orderBy: totalPnl,
    orderDirection: desc,
    where: {
      totalTrades_gte: 10,
      totalVolume_gte: "100",
      lastTradeTimestamp_gte: $startTime
    }
  ) {
    id
    address
    totalPnl
    totalVolume
    totalTrades
    winningTrades
    losingTrades
    lastTradeTimestamp
    positions(first: 5, orderBy: timestamp, orderDirection: desc) {
      id
      market {
        id
        question
      }
      outcome
      amount
      entryPrice
      exitPrice
      realized
    }
  }
}
"""
"""
TOP_TRADERS_QUERY fetches the highest-performing traders based on total P&L.

Filters:
- Minimum 10 trades (excludes inactive/new traders)
- Minimum $100 volume (excludes test accounts)
- Active within specified timeframe

Returns:
- User profile (address, P&L, volumes, trade stats)
- Recent 5 positions for each trader
- Win/loss statistics for calculating win rate

Usage Example:
    variables = {
        "startTime": int(datetime.now().timestamp()) - (7 * 24 * 60 * 60),
        "limit": 100
    }
"""


TRADER_DETAILS_QUERY = """
query GetTraderDetails($address: String!) {
  user(id: $address) {
    id
    address
    totalPnl
    totalVolume
    totalTrades
    winningTrades
    losingTrades
    avgTradeSize
    lastTradeTimestamp
    createdAt
  }
}
"""
"""
TRADER_DETAILS_QUERY fetches comprehensive statistics for a specific trader.

Returns:
- All-time performance metrics
- Trading volume and average trade size
- Win/loss statistics
- Account creation and last activity timestamps

Usage Example:
    variables = {
        "address": "0x1234567890123456789012345678901234567890"
    }
"""


TRADER_POSITIONS_QUERY = """
query GetTraderPositions($address: String!, $limit: Int!, $skip: Int!) {
  positions(
    first: $limit,
    skip: $skip,
    orderBy: timestamp,
    orderDirection: desc,
    where: { user: $address }
  ) {
    id
    market {
      id
      question
      category
      endDate
    }
    outcome
    amount
    entryPrice
    exitPrice
    currentPrice
    realized
    unrealized
    status
    timestamp
  }
}
"""
"""
TRADER_POSITIONS_QUERY fetches individual positions/trades for a trader.

Features:
- Pagination support via skip parameter
- Ordered by most recent first
- Includes both open and closed positions
- Full market context (question, category, end date)
- Realized and unrealized P&L

Usage Example:
    variables = {
        "address": "0x1234...",
        "limit": 50,
        "skip": 0  # For pagination: skip=50, skip=100, etc.
    }
"""


TRADER_STATISTICS_QUERY = """
query GetTraderStatistics($address: String!, $startDate: Int!, $endDate: Int!) {
  userDailyStats(
    where: {
      user: $address,
      date_gte: $startDate,
      date_lte: $endDate
    },
    orderBy: date,
    orderDirection: asc
  ) {
    date
    dailyPnl
    dailyVolume
    tradesCount
    winsCount
    lossesCount
  }
}
"""
"""
TRADER_STATISTICS_QUERY fetches time-series data for a trader's daily performance.

Purpose:
- Historical performance analysis
- Trend identification
- Calculating 7-day, 30-day metrics
- Generating performance charts

Returns:
- Daily P&L and volume
- Daily trade counts
- Win/loss breakdown per day

Usage Example:
    # Get last 30 days
    end_date = int(datetime.now().timestamp())
    start_date = end_date - (30 * 24 * 60 * 60)
    
    variables = {
        "address": "0x1234...",
        "startDate": start_date,
        "endDate": end_date
    }
"""


ACTIVE_MARKETS_QUERY = """
query GetActiveMarkets {
  markets(
    first: 100,
    where: { active: true },
    orderBy: volume,
    orderDirection: desc
  ) {
    id
    question
    category
    volume
    endDate
    outcomes
  }
}
"""
"""
ACTIVE_MARKETS_QUERY fetches currently active prediction markets by volume.

Returns:
- Top 100 most active markets
- Market details (question, category)
- Trading volume
- Market end date
- Possible outcomes (YES/NO or custom)

Usage:
- Display trending markets
- Market discovery
- Volume analysis
- Portfolio diversification suggestions
"""


# ============================================================================
# Additional Query Templates
# ============================================================================

TRADER_MARKETS_QUERY = """
query GetTraderMarkets($address: String!) {
  positions(
    where: { user: $address },
    orderBy: timestamp,
    orderDirection: desc
  ) {
    market {
      id
      question
      category
      volume
      liquidity
      endDate
      outcomes
    }
  }
}
"""
"""
TRADER_MARKETS_QUERY fetches all unique markets a trader has participated in.

Returns:
- Deduplicated list of markets
- Market fundamentals (liquidity, volume)
- Market metadata

Note: Deduplication should be done client-side after fetching.
"""


MARKET_DETAILS_QUERY = """
query GetMarketDetails($marketId: String!) {
  market(id: $marketId) {
    id
    question
    category
    description
    volume
    liquidity
    endDate
    outcomes
    active
    createdAt
    positions(first: 100, orderBy: timestamp, orderDirection: desc) {
      id
      user {
        address
      }
      outcome
      amount
      entryPrice
      exitPrice
      realized
      timestamp
    }
  }
}
"""
"""
MARKET_DETAILS_QUERY fetches comprehensive information about a specific market.

Returns:
- Market fundamentals
- Recent positions (top 100 traders)
- Activity timeline
- Liquidity and volume metrics

Usage:
- Market analysis
- Identifying market trends
- Finding successful traders in specific markets
"""


LEADERBOARD_QUERY = """
query GetLeaderboard($startTime: Int!, $limit: Int!, $skip: Int!) {
  users(
    first: $limit,
    skip: $skip,
    orderBy: totalPnl,
    orderDirection: desc,
    where: {
      totalTrades_gte: 10,
      totalVolume_gte: "100",
      lastTradeTimestamp_gte: $startTime
    }
  ) {
    id
    address
    totalPnl
    totalVolume
    totalTrades
    winningTrades
    losingTrades
    avgTradeSize
    lastTradeTimestamp
  }
}
"""
"""
LEADERBOARD_QUERY is optimized for paginated leaderboard displays.

Features:
- Pagination support
- Filters for active, established traders
- Minimal data for fast response
- Sorted by total P&L

Usage:
- Display leaderboards
- Paginated trader lists
- Performance rankings
"""


# ============================================================================
# GraphQL Query Builder Helper Class
# ============================================================================

class GraphQueryBuilder:
    """
    Helper class for building and managing GraphQL queries for Polymarket subgraph.
    
    Provides utilities for:
    - Building queries with dynamic parameters
    - Converting time ranges to Unix timestamps
    - Validating Ethereum addresses
    - Constructing query variables
    """
    
    @staticmethod
    def build_top_traders_query(
        timeframe_days: int = 7,
        min_trades: int = 10,
        min_volume: Decimal = Decimal("100"),
        limit: int = 100
    ) -> Tuple[str, Dict]:
        """
        Build a query for fetching top traders with custom filters.
        
        Args:
            timeframe_days: Number of days to look back (default: 7)
            min_trades: Minimum number of trades required (default: 10)
            min_volume: Minimum trading volume in USD (default: $100)
            limit: Maximum number of traders to return (default: 100)
            
        Returns:
            Tuple of (query_string, variables_dict)
            
        Example:
            >>> query, variables = GraphQueryBuilder.build_top_traders_query(
            ...     timeframe_days=30,
            ...     min_trades=50,
            ...     min_volume=Decimal("1000"),
            ...     limit=50
            ... )
            >>> # Use with GraphQL client
            >>> result = await client.execute(query, variables)
        """
        # Calculate start time
        start_time = GraphQueryBuilder.build_time_filter(timeframe_days)
        
        # Build custom query with dynamic filters
        query = f"""
        query GetTopTraders($startTime: Int!, $limit: Int!) {{
          users(
            first: $limit,
            orderBy: totalPnl,
            orderDirection: desc,
            where: {{
              totalTrades_gte: {min_trades},
              totalVolume_gte: "{float(min_volume)}",
              lastTradeTimestamp_gte: $startTime
            }}
          ) {{
            id
            address
            totalPnl
            totalVolume
            totalTrades
            winningTrades
            losingTrades
            lastTradeTimestamp
            positions(first: 5, orderBy: timestamp, orderDirection: desc) {{
              id
              market {{
                id
                question
              }}
              outcome
              amount
              entryPrice
              exitPrice
              realized
            }}
          }}
        }}
        """
        
        variables = {
            "startTime": start_time,
            "limit": limit
        }
        
        return (query, variables)
    
    @staticmethod
    def build_trader_details_query(address: str) -> Tuple[str, Dict]:
        """
        Build a query for fetching specific trader details.
        
        Args:
            address: Ethereum wallet address (must be valid)
            
        Returns:
            Tuple of (query_string, variables_dict)
            
        Raises:
            ValueError: If address is invalid
            
        Example:
            >>> query, vars = GraphQueryBuilder.build_trader_details_query("0x123...")
        """
        if not GraphQueryBuilder.validate_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")
        
        variables = {
            "address": address.lower()  # The Graph uses lowercase addresses
        }
        
        return (TRADER_DETAILS_QUERY, variables)
    
    @staticmethod
    def build_positions_query(
        address: str,
        limit: int = 50,
        skip: int = 0
    ) -> Tuple[str, Dict]:
        """
        Build a query for fetching trader positions with pagination.
        
        Args:
            address: Ethereum wallet address
            limit: Number of positions to return (default: 50)
            skip: Number of positions to skip for pagination (default: 0)
            
        Returns:
            Tuple of (query_string, variables_dict)
            
        Example:
            >>> # First page
            >>> query, vars = GraphQueryBuilder.build_positions_query("0x123...", limit=50, skip=0)
            >>> # Second page
            >>> query, vars = GraphQueryBuilder.build_positions_query("0x123...", limit=50, skip=50)
        """
        if not GraphQueryBuilder.validate_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")
        
        variables = {
            "address": address.lower(),
            "limit": limit,
            "skip": skip
        }
        
        return (TRADER_POSITIONS_QUERY, variables)
    
    @staticmethod
    def build_statistics_query(
        address: str,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[str, Dict]:
        """
        Build a query for fetching trader statistics in a date range.
        
        Args:
            address: Ethereum wallet address
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Tuple of (query_string, variables_dict)
            
        Example:
            >>> from datetime import datetime, timedelta
            >>> end = datetime.now()
            >>> start = end - timedelta(days=30)
            >>> query, vars = GraphQueryBuilder.build_statistics_query("0x123...", start, end)
        """
        if not GraphQueryBuilder.validate_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")
        
        variables = {
            "address": address.lower(),
            "startDate": int(start_date.timestamp()),
            "endDate": int(end_date.timestamp())
        }
        
        return (TRADER_STATISTICS_QUERY, variables)
    
    @staticmethod
    def build_time_filter(days: int) -> int:
        """
        Convert days to Unix timestamp for GraphQL queries.
        
        Args:
            days: Number of days to look back from now
            
        Returns:
            Unix timestamp (seconds since epoch)
            
        Example:
            >>> timestamp = GraphQueryBuilder.build_time_filter(7)
            >>> # Returns timestamp from 7 days ago
        """
        if days < 0:
            raise ValueError("Days must be positive")
        
        lookback_time = datetime.utcnow() - timedelta(days=days)
        return int(lookback_time.timestamp())
    
    @staticmethod
    def validate_address(address: str) -> bool:
        """
        Validate Ethereum address format.
        
        An Ethereum address must:
        - Start with '0x'
        - Be exactly 42 characters long
        - Contain only hexadecimal characters (0-9, a-f, A-F)
        
        Args:
            address: String to validate as Ethereum address
            
        Returns:
            True if valid, False otherwise
            
        Example:
            >>> GraphQueryBuilder.validate_address("0x1234567890123456789012345678901234567890")
            True
            >>> GraphQueryBuilder.validate_address("0xinvalid")
            False
        """
        if not address:
            return False
        
        # Must start with 0x
        if not address.startswith('0x'):
            return False
        
        # Must be exactly 42 characters (0x + 40 hex chars)
        if len(address) != 42:
            return False
        
        # Must contain only valid hex characters
        hex_pattern = re.compile(r'^0x[0-9a-fA-F]{40}$')
        if not hex_pattern.match(address):
            return False
        
        return True
    
    @staticmethod
    def build_leaderboard_query(
        timeframe_days: int = 7,
        limit: int = 100,
        skip: int = 0
    ) -> Tuple[str, Dict]:
        """
        Build a paginated leaderboard query.
        
        Args:
            timeframe_days: Activity timeframe (default: 7 days)
            limit: Number of traders per page (default: 100)
            skip: Number to skip for pagination (default: 0)
            
        Returns:
            Tuple of (query_string, variables_dict)
            
        Example:
            >>> # Page 1
            >>> query, vars = GraphQueryBuilder.build_leaderboard_query(limit=50, skip=0)
            >>> # Page 2
            >>> query, vars = GraphQueryBuilder.build_leaderboard_query(limit=50, skip=50)
        """
        start_time = GraphQueryBuilder.build_time_filter(timeframe_days)
        
        variables = {
            "startTime": start_time,
            "limit": limit,
            "skip": skip
        }
        
        return (LEADERBOARD_QUERY, variables)
    
    @staticmethod
    def normalize_address(address: str) -> str:
        """
        Normalize an Ethereum address for The Graph queries.
        
        The Graph stores addresses in lowercase, so we need to normalize
        input addresses for consistent querying.
        
        Args:
            address: Ethereum address (any case)
            
        Returns:
            Lowercase address
            
        Raises:
            ValueError: If address is invalid
            
        Example:
            >>> GraphQueryBuilder.normalize_address("0xABC123...")
            "0xabc123..."
        """
        if not GraphQueryBuilder.validate_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")
        
        return address.lower()


# ============================================================================
# Query Metadata
# ============================================================================

QUERY_DESCRIPTIONS = {
    "TOP_TRADERS_QUERY": "Fetch top traders by P&L with activity filters",
    "TRADER_DETAILS_QUERY": "Get comprehensive stats for specific trader",
    "TRADER_POSITIONS_QUERY": "Fetch trader positions with pagination",
    "TRADER_STATISTICS_QUERY": "Get time-series daily statistics",
    "ACTIVE_MARKETS_QUERY": "Fetch active markets by volume",
    "TRADER_MARKETS_QUERY": "Get markets a trader participated in",
    "MARKET_DETAILS_QUERY": "Comprehensive market information",
    "LEADERBOARD_QUERY": "Paginated leaderboard query"
}


def get_query_description(query_name: str) -> str:
    """Get human-readable description of a query."""
    return QUERY_DESCRIPTIONS.get(query_name, "No description available")


# ============================================================================
# Export All
# ============================================================================

__all__ = [
    # Query Templates
    'TOP_TRADERS_QUERY',
    'TRADER_DETAILS_QUERY',
    'TRADER_POSITIONS_QUERY',
    'TRADER_STATISTICS_QUERY',
    'ACTIVE_MARKETS_QUERY',
    'TRADER_MARKETS_QUERY',
    'MARKET_DETAILS_QUERY',
    'LEADERBOARD_QUERY',
    
    # Builder Class
    'GraphQueryBuilder',
    
    # Utilities
    'get_query_description',
]
