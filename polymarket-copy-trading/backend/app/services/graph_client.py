"""
Service class for interacting with The Graph Protocol's Polymarket subgraph.

This service provides async methods to fetch trader data, positions, and market
information from Polymarket's subgraph on The Graph Protocol.
"""

import httpx
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from app.core.config import settings

logger = logging.getLogger(__name__)


class PolymarketGraphClient:
    """
    Client for querying Polymarket data from The Graph Protocol.
    
    This client handles all GraphQL queries to the Polymarket subgraph,
    including trader statistics, positions, and market data.
    """
    
    # The Graph Polymarket Subgraph URL
    SUBGRAPH_URL = "https://api.thegraph.com/subgraphs/name/polymarket/matic-markets-5"
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    RETRY_BACKOFF = 2.0  # exponential backoff multiplier
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Graph client.
        
        Args:
            api_key: Optional API key for The Graph (for higher rate limits)
        """
        self.api_key = api_key or getattr(settings, 'GRAPH_API_KEY', None)
        self.test_mode = not self.api_key
        
        # Configure httpx client
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers=headers,
            http2=True
        )
        
        if self.test_mode:
            logger.warning("Graph client running in TEST MODE with mocked data")
        
        logger.info(f"Initialized PolymarketGraphClient (test_mode={self.test_mode})")
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def get_top_traders(
        self,
        limit: int = 100,
        timeframe_days: int = 7
    ) -> List[Dict]:
        """
        Get top traders by P&L in the specified timeframe.
        
        Args:
            limit: Maximum number of traders to return (default 100)
            timeframe_days: Number of days to look back (default 7)
            
        Returns:
            List of trader dictionaries with performance metrics
            
        Example:
            >>> traders = await client.get_top_traders(limit=10, timeframe_days=7)
            >>> print(traders[0])
            {
                'wallet_address': '0x123...',
                'total_volume': 125000.50,
                'realized_pnl': 12450.75,
                'total_trades': 145,
                'win_rate': 68.5,
            }
        """
        if self.test_mode:
            return self._get_mock_top_traders(limit)
        
        start_time = datetime.utcnow()
        
        # Calculate timestamp for timeframe
        cutoff_timestamp = int((datetime.utcnow() - timedelta(days=timeframe_days)).timestamp())
        
        query = """
        query GetTopTraders($first: Int!, $minTrades: Int!, $minVolume: String!, $timestamp: Int!) {
            users(
                first: $first,
                orderBy: realizedPnl,
                orderDirection: desc,
                where: {
                    numTrades_gte: $minTrades,
                    totalVolume_gte: $minVolume,
                    lastTradeTimestamp_gte: $timestamp
                }
            ) {
                id
                address
                totalVolume
                realizedPnl
                numTrades
                numMarkets
                lastTradeTimestamp
                positions(first: 1000, where: { createdAtTimestamp_gte: $timestamp }) {
                    id
                    side
                    outcome
                    entryPrice
                    exitPrice
                    quantity
                    market {
                        id
                        question
                    }
                }
            }
        }
        """
        
        variables = {
            "first": limit,
            "minTrades": 10,
            "minVolume": "100",  # $100 minimum volume
            "timestamp": cutoff_timestamp
        }
        
        try:
            response = await self._execute_query(query, variables)
            traders = self._parse_traders_response(response, timeframe_days)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Fetched {len(traders)} top traders in {duration:.2f}s")
            
            return traders
            
        except Exception as e:
            logger.error(f"Error fetching top traders: {e}")
            return []
    
    async def get_trader_details(self, wallet_address: str) -> Optional[Dict]:
        """
        Get detailed statistics for a specific trader.
        
        Args:
            wallet_address: Ethereum wallet address (0x...)
            
        Returns:
            Dictionary with trader details or None if not found
            
        Example:
            >>> details = await client.get_trader_details('0x123...')
            >>> print(details)
            {
                'wallet_address': '0x123...',
                'all_time_pnl': 12450.75,
                'pnl_7d': 2450.50,
                'pnl_30d': 8920.75,
                'win_rate': 68.5,
                'total_trades': 145,
                'markets_traded': 23,
                'total_volume': 125000.50,
                'last_trade_at': '2025-01-01T12:00:00Z'
            }
        """
        if self.test_mode:
            return self._get_mock_trader_details(wallet_address)
        
        # Validate wallet address
        if not self._is_valid_address(wallet_address):
            logger.error(f"Invalid wallet address: {wallet_address}")
            return None
        
        start_time = datetime.utcnow()
        
        # Calculate timestamps
        timestamp_7d = int((datetime.utcnow() - timedelta(days=7)).timestamp())
        timestamp_30d = int((datetime.utcnow() - timedelta(days=30)).timestamp())
        
        query = """
        query GetTraderDetails($address: String!, $timestamp7d: Int!, $timestamp30d: Int!) {
            user(id: $address) {
                id
                address
                totalVolume
                realizedPnl
                numTrades
                numMarkets
                lastTradeTimestamp
                positions(first: 1000, orderBy: createdAtTimestamp, orderDirection: desc) {
                    id
                    side
                    outcome
                    entryPrice
                    exitPrice
                    quantity
                    size
                    realizedPnl
                    createdAtTimestamp
                    closedAtTimestamp
                    market {
                        id
                        question
                    }
                }
            }
        }
        """
        
        variables = {
            "address": wallet_address.lower(),
            "timestamp7d": timestamp_7d,
            "timestamp30d": timestamp_30d
        }
        
        try:
            response = await self._execute_query(query, variables)
            
            if not response.get('data', {}).get('user'):
                logger.warning(f"Trader not found: {wallet_address}")
                return None
            
            trader = self._parse_trader_details(response, timestamp_7d, timestamp_30d)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Fetched trader details for {wallet_address} in {duration:.2f}s")
            
            return trader
            
        except Exception as e:
            logger.error(f"Error fetching trader details for {wallet_address}: {e}")
            return None
    
    async def get_trader_positions(
        self,
        wallet_address: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get recent positions/trades for a trader.
        
        Args:
            wallet_address: Ethereum wallet address
            limit: Maximum number of positions to return
            
        Returns:
            List of position dictionaries
            
        Example:
            >>> positions = await client.get_trader_positions('0x123...', limit=10)
            >>> print(positions[0])
            {
                'position_id': 'pos_123',
                'market_id': '0xmarket123',
                'market_name': 'Will Bitcoin hit $100k?',
                'side': 'YES',
                'entry_price': 0.72,
                'exit_price': 0.85,
                'quantity': 100.5,
                'pnl': 125.50,
                'status': 'CLOSED',
                'created_at': '2025-01-01T10:00:00Z',
                'closed_at': '2025-01-02T15:30:00Z'
            }
        """
        if self.test_mode:
            return self._get_mock_positions(wallet_address, limit)
        
        if not self._is_valid_address(wallet_address):
            logger.error(f"Invalid wallet address: {wallet_address}")
            return []
        
        query = """
        query GetTraderPositions($address: String!, $first: Int!) {
            positions(
                first: $first,
                where: { user: $address },
                orderBy: createdAtTimestamp,
                orderDirection: desc
            ) {
                id
                side
                outcome
                entryPrice
                exitPrice
                quantity
                size
                realizedPnl
                createdAtTimestamp
                closedAtTimestamp
                market {
                    id
                    question
                    outcomes
                }
            }
        }
        """
        
        variables = {
            "address": wallet_address.lower(),
            "first": limit
        }
        
        try:
            response = await self._execute_query(query, variables)
            positions = self._parse_positions_response(response)
            
            logger.info(f"Fetched {len(positions)} positions for {wallet_address}")
            return positions
            
        except Exception as e:
            logger.error(f"Error fetching positions for {wallet_address}: {e}")
            return []
    
    async def get_trader_markets(self, wallet_address: str) -> List[Dict]:
        """
        Get unique markets a trader has participated in.
        
        Args:
            wallet_address: Ethereum wallet address
            
        Returns:
            List of market dictionaries
        """
        if self.test_mode:
            return self._get_mock_markets(wallet_address)
        
        if not self._is_valid_address(wallet_address):
            return []
        
        query = """
        query GetTraderMarkets($address: String!) {
            user(id: $address) {
                positions(first: 1000) {
                    market {
                        id
                        question
                        outcomes
                        volume
                        liquidity
                        endDate
                    }
                }
            }
        }
        """
        
        variables = {"address": wallet_address.lower()}
        
        try:
            response = await self._execute_query(query, variables)
            markets = self._parse_markets_response(response)
            
            logger.info(f"Fetched {len(markets)} markets for {wallet_address}")
            return markets
            
        except Exception as e:
            logger.error(f"Error fetching markets for {wallet_address}: {e}")
            return []
    
    # ========================================================================
    # Private Helper Methods
    # ========================================================================
    
    async def _execute_query(
        self,
        query: str,
        variables: Dict,
        retry_count: int = 0
    ) -> Dict:
        """
        Execute a GraphQL query with retry logic.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            retry_count: Current retry attempt
            
        Returns:
            Parsed GraphQL response
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        payload = {
            "query": query,
            "variables": variables
        }
        
        try:
            response = await self.client.post(self.SUBGRAPH_URL, json=payload)
            
            # Log rate limit headers if present
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = response.headers['X-RateLimit-Remaining']
                logger.debug(f"Rate limit remaining: {remaining}")
            
            response.raise_for_status()
            data = response.json()
            
            if 'errors' in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                raise Exception(f"GraphQL query failed: {data['errors']}")
            
            return data
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limited
                if retry_count < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY * (self.RETRY_BACKOFF ** retry_count)
                    logger.warning(f"Rate limited, retrying in {delay}s (attempt {retry_count + 1}/{self.MAX_RETRIES})")
                    await asyncio.sleep(delay)
                    return await self._execute_query(query, variables, retry_count + 1)
                else:
                    logger.error("Max retries reached for rate limiting")
                    raise
            else:
                logger.error(f"HTTP error {e.response.status_code}: {e}")
                raise
                
        except httpx.TimeoutException:
            if retry_count < self.MAX_RETRIES:
                delay = self.RETRY_DELAY * (self.RETRY_BACKOFF ** retry_count)
                logger.warning(f"Timeout, retrying in {delay}s (attempt {retry_count + 1}/{self.MAX_RETRIES})")
                await asyncio.sleep(delay)
                return await self._execute_query(query, variables, retry_count + 1)
            else:
                logger.error("Max retries reached for timeout")
                raise
    
    def _parse_traders_response(self, response: Dict, timeframe_days: int) -> List[Dict]:
        """Parse and normalize traders from Graph response."""
        users = response.get('data', {}).get('users', [])
        traders = []
        
        for user in users:
            positions = user.get('positions', [])
            win_rate = self._calculate_win_rate(positions)
            pnl = self._calculate_pnl(positions)
            
            trader = {
                'wallet_address': user.get('address', user.get('id')),
                'total_volume': float(user.get('totalVolume', 0)),
                'realized_pnl': float(user.get('realizedPnl', 0)),
                'total_trades': int(user.get('numTrades', 0)),
                'markets_traded': int(user.get('numMarkets', 0)),
                'win_rate': win_rate,
                'last_trade_at': datetime.fromtimestamp(int(user.get('lastTradeTimestamp', 0))).isoformat() if user.get('lastTradeTimestamp') else None,
            }
            traders.append(trader)
        
        return traders
    
    def _parse_trader_details(self, response: Dict, timestamp_7d: int, timestamp_30d: int) -> Dict:
        """Parse detailed trader information."""
        user = response['data']['user']
        positions = user.get('positions', [])
        
        # Calculate time-based P&L
        pnl_7d = sum(
            float(p.get('realizedPnl', 0))
            for p in positions
            if int(p.get('createdAtTimestamp', 0)) >= timestamp_7d
        )
        
        pnl_30d = sum(
            float(p.get('realizedPnl', 0))
            for p in positions
            if int(p.get('createdAtTimestamp', 0)) >= timestamp_30d
        )
        
        return {
            'wallet_address': user.get('address', user.get('id')),
            'all_time_pnl': float(user.get('realizedPnl', 0)),
            'pnl_7d': pnl_7d,
            'pnl_30d': pnl_30d,
            'win_rate': self._calculate_win_rate(positions),
            'total_trades': int(user.get('numTrades', 0)),
            'markets_traded': int(user.get('numMarkets', 0)),
            'total_volume': float(user.get('totalVolume', 0)),
            'last_trade_at': datetime.fromtimestamp(int(user.get('lastTradeTimestamp', 0))).isoformat() if user.get('lastTradeTimestamp') else None,
        }
    
    def _parse_positions_response(self, response: Dict) -> List[Dict]:
        """Parse positions from Graph response."""
        positions_data = response.get('data', {}).get('positions', [])
        positions = []
        
        for pos in positions_data:
            market = pos.get('market', {})
            closed_at = pos.get('closedAtTimestamp')
            
            position = {
                'position_id': pos.get('id'),
                'market_id': market.get('id'),
                'market_name': market.get('question'),
                'side': pos.get('outcome', pos.get('side', 'YES')),
                'entry_price': float(pos.get('entryPrice', 0)),
                'exit_price': float(pos.get('exitPrice', 0)) if pos.get('exitPrice') else None,
                'quantity': float(pos.get('quantity', 0)),
                'pnl': float(pos.get('realizedPnl', 0)),
                'status': 'CLOSED' if closed_at else 'OPEN',
                'created_at': datetime.fromtimestamp(int(pos.get('createdAtTimestamp', 0))).isoformat() if pos.get('createdAtTimestamp') else None,
                'closed_at': datetime.fromtimestamp(int(closed_at)).isoformat() if closed_at else None,
            }
            positions.append(position)
        
        return positions
    
    def _parse_markets_response(self, response: Dict) -> List[Dict]:
        """Parse unique markets from user positions."""
        user = response.get('data', {}).get('user', {})
        positions = user.get('positions', [])
        
        # Get unique markets
        markets_dict = {}
        for pos in positions:
            market = pos.get('market', {})
            market_id = market.get('id')
            
            if market_id and market_id not in markets_dict:
                markets_dict[market_id] = {
                    'market_id': market_id,
                    'market_name': market.get('question'),
                    'outcomes': market.get('outcomes', []),
                    'volume': float(market.get('volume', 0)),
                    'liquidity': float(market.get('liquidity', 0)),
                    'end_date': market.get('endDate'),
                }
        
        return list(markets_dict.values())
    
    def _calculate_win_rate(self, positions: List[Dict]) -> float:
        """
        Calculate win rate from positions.
        
        Args:
            positions: List of position dictionaries
            
        Returns:
            Win rate as a percentage (0-100)
        """
        if not positions:
            return 0.0
        
        closed_positions = [p for p in positions if p.get('closedAtTimestamp') or p.get('exitPrice')]
        if not closed_positions:
            return 0.0
        
        winning = sum(1 for p in closed_positions if float(p.get('realizedPnl', 0)) > 0)
        return (winning / len(closed_positions)) * 100 if closed_positions else 0.0
    
    def _calculate_pnl(self, positions: List[Dict]) -> Decimal:
        """Calculate total P&L from positions."""
        total = sum(Decimal(str(p.get('realizedPnl', 0))) for p in positions)
        return total
    
    def _is_valid_address(self, address: str) -> bool:
        """Validate Ethereum address format."""
        if not address:
            return False
        if not address.startswith('0x'):
            return False
        if len(address) != 42:
            return False
        try:
            int(address, 16)
            return True
        except ValueError:
            return False
    
    # ========================================================================
    # Mock Data Methods (Test Mode)
    # ========================================================================
    
    def _get_mock_top_traders(self, limit: int) -> List[Dict]:
        """Return mock trader data for testing."""
        mock_traders = [
            {
                'wallet_address': f'0x{i:040x}',
                'total_volume': 125000.50 - (i * 5000),
                'realized_pnl': 12450.75 - (i * 500),
                'total_trades': 145 - (i * 5),
                'markets_traded': 23 - i,
                'win_rate': 68.5 - (i * 0.5),
                'last_trade_at': datetime.utcnow().isoformat(),
            }
            for i in range(min(limit, 10))
        ]
        return mock_traders
    
    def _get_mock_trader_details(self, wallet_address: str) -> Dict:
        """Return mock trader details for testing."""
        return {
            'wallet_address': wallet_address,
            'all_time_pnl': 12450.75,
            'pnl_7d': 2450.50,
            'pnl_30d': 8920.75,
            'win_rate': 68.5,
            'total_trades': 145,
            'markets_traded': 23,
            'total_volume': 125000.50,
            'last_trade_at': datetime.utcnow().isoformat(),
        }
    
    def _get_mock_positions(self, wallet_address: str, limit: int) -> List[Dict]:
        """Return mock positions for testing."""
        return [
            {
                'position_id': f'pos_{i}',
                'market_id': f'0xmarket{i:040x}',
                'market_name': f'Mock Market {i}',
                'side': 'YES' if i % 2 == 0 else 'NO',
                'entry_price': 0.70 + (i * 0.01),
                'exit_price': 0.85 if i % 3 == 0 else None,
                'quantity': 100.0 + (i * 10),
                'pnl': 125.50 if i % 3 == 0 else 0.0,
                'status': 'CLOSED' if i % 3 == 0 else 'OPEN',
                'created_at': (datetime.utcnow() - timedelta(days=i)).isoformat(),
                'closed_at': (datetime.utcnow() - timedelta(days=i-1)).isoformat() if i % 3 == 0 else None,
            }
            for i in range(min(limit, 10))
        ]
    
    def _get_mock_markets(self, wallet_address: str) -> List[Dict]:
        """Return mock markets for testing."""
        return [
            {
                'market_id': f'0xmarket{i:040x}',
                'market_name': f'Mock Market Question {i}',
                'outcomes': ['YES', 'NO'],
                'volume': 50000.0 + (i * 1000),
                'liquidity': 25000.0 + (i * 500),
                'end_date': (datetime.utcnow() + timedelta(days=30 + i)).isoformat(),
            }
            for i in range(5)
        ]


# Singleton instance
graph_client = PolymarketGraphClient()
