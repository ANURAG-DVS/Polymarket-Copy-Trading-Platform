"""
Web3 Provider Configuration Service

Manages RPC connections to Polygon network with:
- Primary and fallback RPC endpoints
- Connection health monitoring
- Automatic failover
- Request caching
"""

import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.middleware import async_geth_poa_middleware
from loguru import logger

from app.core.config import settings


@dataclass
class RPCEndpoint:
    """RPC endpoint configuration"""
    url: str
    name: str
    priority: int = 0  # Lower = higher priority
    is_websocket: bool = False
    
    # Health tracking
    is_healthy: bool = True
    last_checked: Optional[datetime] = None
    consecutive_failures: int = 0
    average_latency_ms: float = 0.0
    
    # Statistics
    total_requests: int = 0
    total_failures: int = 0


@dataclass
class RPCProviderConfig:
    """Configuration for RPC providers"""
    endpoints: List[RPCEndpoint] = field(default_factory=list)
    
    # Health check settings
    health_check_interval: int = 60  # seconds
    max_consecutive_failures: int = 3
    
    # Request settings
    request_timeout: int = 30  # seconds
    max_retries: int = 3
    
    # Caching
    cache_ttl: int = 10  # seconds
    enable_caching: bool = True


class Web3ProviderService:
    """
    Web3 provider with automatic failover and health monitoring.
    
    Features:
    - Multiple RPC endpoints with priority-based selection
    - Automatic failover on connection errors
    - Health monitoring with periodic checks
    - Request caching for frequently accessed data
    - Latency tracking
    """
    
    def __init__(self, config: Optional[RPCProviderConfig] = None):
        """
        Initialize Web3 provider service.
        
        Args:
            config: RPC provider configuration (uses settings if None)
        """
        self.config = config or self._load_config_from_settings()
        self.w3: Optional[AsyncWeb3] = None
        self.current_endpoint: Optional[RPCEndpoint] = None
        
        # Request cache
        self._cache: Dict[str, tuple[Any, datetime]] = {}
        
        # Health check task
        self._health_check_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"Web3ProviderService initialized with {len(self.config.endpoints)} endpoints"
        )
    
    def _load_config_from_settings(self) -> RPCProviderConfig:
        """Load RPC configuration from settings"""
        endpoints = []
        
        # Primary endpoint
        if settings.POLYGON_RPC_URL:
            endpoints.append(RPCEndpoint(
                url=settings.POLYGON_RPC_URL,
                name="Primary (Alchemy/Infura)",
                priority=0,
                is_websocket=False
            ))
        
        # WebSocket endpoint
        if settings.POLYGON_RPC_WSS:
            endpoints.append(RPCEndpoint(
                url=settings.POLYGON_RPC_WSS,
                name="WebSocket",
                priority=1,
                is_websocket=True
            ))
        
        # Fallback endpoints
        fallback_urls = settings.POLYGON_RPC_FALLBACKS or []
        for i, url in enumerate(fallback_urls):
            endpoints.append(RPCEndpoint(
                url=url,
                name=f"Fallback {i+1}",
                priority=10 + i,
                is_websocket='wss://' in url
            ))
        
        return RPCProviderConfig(endpoints=endpoints)
    
    async def connect(self) -> AsyncWeb3:
        """
        Connect to Polygon RPC endpoint.
        
        Returns:
            Connected Web3 instance
            
        Raises:
            ConnectionError: If unable to connect to any endpoint
        """
        # Try endpoints in priority order
        sorted_endpoints = sorted(
            [e for e in self.config.endpoints if e.is_healthy],
            key=lambda x: (x.priority, x.average_latency_ms)
        )
        
        if not sorted_endpoints:
            # All unhealthy, try all again
            sorted_endpoints = sorted(
                self.config.endpoints,
                key=lambda x: x.priority
            )
        
        for endpoint in sorted_endpoints:
            try:
                w3 = await self._connect_to_endpoint(endpoint)
                
                # Test connection
                await w3.eth.block_number
                
                self.w3 = w3
                self.current_endpoint = endpoint
                
                # Mark as healthy
                endpoint.is_healthy = True
                endpoint.consecutive_failures = 0
                
                logger.info(f"Connected to {endpoint.name}: {endpoint.url}")
                
                # Start health monitoring
                if not self._health_check_task:
                    self._health_check_task = asyncio.create_task(
                        self._health_check_loop()
                    )
                
                return w3
                
            except Exception as e:
                endpoint.consecutive_failures += 1
                endpoint.total_failures += 1
                
                if endpoint.consecutive_failures >= self.config.max_consecutive_failures:
                    endpoint.is_healthy = False
                
                logger.warning(
                    f"Failed to connect to {endpoint.name}: {e}. "
                    f"Failures: {endpoint.consecutive_failures}"
                )
                continue
        
        raise ConnectionError("Unable to connect to any RPC endpoint")
    
    async def _connect_to_endpoint(self, endpoint: RPCEndpoint) -> AsyncWeb3:
        """Connect to a specific RPC endpoint"""
        if endpoint.is_websocket:
            from web3 import AsyncWeb3
            from web3.providers.websocket import WebSocketProvider
            
            # WebSocket provider
            provider = WebSocketProvider(
                endpoint.url,
                websocket_timeout=self.config.request_timeout
            )
        else:
            # HTTP provider
            provider = AsyncHTTPProvider(
                endpoint.url,
                request_kwargs={'timeout': self.config.request_timeout}
            )
        
        w3 = AsyncWeb3(provider)
        
        # Add PoA middleware for Polygon
        w3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
        
        return w3
    
    async def get_web3(self) -> AsyncWeb3:
        """
        Get connected Web3 instance.
        
        Returns:
            AsyncWeb3 instance
            
        Raises:
            ConnectionError: If not connected
        """
        if not self.w3:
            await self.connect()
        
        return self.w3
    
    async def execute_with_retry(
        self,
        method_name: str,
        *args,
        cache_key: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Execute Web3 method with automatic retry and failover.
        
        Args:
            method_name: Method to call (e.g., 'eth.get_block')
            *args: Method arguments
            cache_key: Optional cache key for caching results
            **kwargs: Method keyword arguments
            
        Returns:
            Method result
            
        Raises:
            Exception: If all retries fail
        """
        # Check cache
        if cache_key and self.config.enable_caching:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached
        
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                w3 = await self.get_web3()
                
                # Navigate to method
                obj = w3
                for part in method_name.split('.'):
                    obj = getattr(obj, part)
                
                # Track latency
                start_time = datetime.utcnow()
                
                # Execute method
                if asyncio.iscoroutinefunction(obj):
                    result = await obj(*args, **kwargs)
                else:
                    result = obj(*args, **kwargs)
                
                # Update latency tracking
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                self._update_latency(latency_ms)
                
                # Update stats
                if self.current_endpoint:
                    self.current_endpoint.total_requests += 1
                
                # Cache result
                if cache_key and self.config.enable_caching:
                    self._add_to_cache(cache_key, result)
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.config.max_retries}): {e}"
                )
                
                # Mark current endpoint as potentially unhealthy
                if self.current_endpoint:
                    self.current_endpoint.consecutive_failures += 1
                    self.current_endpoint.total_failures += 1
                
                # Try to reconnect to different endpoint
                try:
                    await self.connect()
                except ConnectionError:
                    if attempt == self.config.max_retries - 1:
                        raise
                
                # Wait before retry
                await asyncio.sleep(2 ** attempt)
        
        raise last_error or Exception("Request failed after all retries")
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.utcnow() - timestamp < timedelta(seconds=self.config.cache_ttl):
                return value
            else:
                del self._cache[key]
        return None
    
    def _add_to_cache(self, key: str, value: Any):
        """Add value to cache"""
        self._cache[key] = (value, datetime.utcnow())
    
    def _update_latency(self, latency_ms: float):
        """Update average latency for current endpoint"""
        if self.current_endpoint:
            # Exponential moving average
            alpha = 0.3
            if self.current_endpoint.average_latency_ms == 0:
                self.current_endpoint.average_latency_ms = latency_ms
            else:
                self.current_endpoint.average_latency_ms = (
                    alpha * latency_ms + 
                    (1 - alpha) * self.current_endpoint.average_latency_ms
                )
    
    async def _health_check_loop(self):
        """Periodically check health of all endpoints"""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_all_endpoints()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _check_all_endpoints(self):
        """Check health of all endpoints"""
        for endpoint in self.config.endpoints:
            try:
                # Create temporary connection
                w3 = await self._connect_to_endpoint(endpoint)
                
                # Quick health check
                start = datetime.utcnow()
                await w3.eth.block_number
                latency = (datetime.utcnow() - start).total_seconds() * 1000
                
                # Update health status
                endpoint.is_healthy = True
                endpoint.consecutive_failures = 0
                endpoint.last_checked = datetime.utcnow()
                endpoint.average_latency_ms = latency
                
                logger.debug(
                    f"Health check passed: {endpoint.name} ({latency:.2f}ms)"
                )
                
            except Exception as e:
                endpoint.consecutive_failures += 1
                endpoint.last_checked = datetime.utcnow()
                
                if endpoint.consecutive_failures >= self.config.max_consecutive_failures:
                    endpoint.is_healthy = False
                
                logger.warning(
                    f"Health check failed: {endpoint.name} - {e}"
                )
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all endpoints"""
        return {
            'current_endpoint': self.current_endpoint.name if self.current_endpoint else None,
            'current_url': self.current_endpoint.url if self.current_endpoint else None,
            'endpoints': [
                {
                    'name': e.name,
                    'url': e.url,
                    'healthy': e.is_healthy,
                    'latency_ms': round(e.average_latency_ms, 2),
                    'total_requests': e.total_requests,
                    'total_failures': e.total_failures,
                    'last_checked': e.last_checked.isoformat() if e.last_checked else None
                }
                for e in self.config.endpoints
            ],
            'cache_size': len(self._cache)
        }
    
    async def close(self):
        """Close connections and cleanup"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        if self.w3 and hasattr(self.w3.provider, 'disconnect'):
            await self.w3.provider.disconnect()
        
        logger.info("Web3ProviderService closed")


# Singleton instance
_web3_provider_service: Optional[Web3ProviderService] = None


def get_web3_provider_service() -> Web3ProviderService:
    """Get singleton instance of Web3ProviderService"""
    global _web3_provider_service
    if _web3_provider_service is None:
        _web3_provider_service = Web3ProviderService()
    return _web3_provider_service
