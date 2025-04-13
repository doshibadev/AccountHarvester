import requests
import time
import json
import os
import gzip
import shutil
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from utils.logger import logger
from config.settings import settings
from core.proxy_manager import proxy_manager
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import hashlib
import threading

class SteamAPIError(Exception):
    """Exception raised for Steam API errors"""
    pass

class RateLimiter:
    """Token bucket rate limiter for Steam API requests"""
    
    def __init__(self, tokens_per_second: float = 1.0, max_tokens: int = 10):
        self.tokens_per_second = tokens_per_second
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.last_refill_time = time.time()
        self.lock = threading.Lock()
    
    def refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        time_passed = now - self.last_refill_time
        new_tokens = time_passed * self.tokens_per_second
        self.tokens = min(self.tokens + new_tokens, self.max_tokens)
        self.last_refill_time = now
    
    def consume(self, tokens: int = 1) -> float:
        """
        Consume tokens from the bucket. If not enough tokens are available,
        return the time needed to wait in seconds.
        
        Returns:
            float: 0 if tokens were consumed, or wait time in seconds
        """
        with self.lock:
            self.refill_tokens()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0
            else:
                # Calculate how long until enough tokens are available
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.tokens_per_second
                return wait_time

class CacheEntry:
    """Represents a cached API response"""
    def __init__(self, data: Any, expiry: datetime):
        self.data = data
        self.expiry = expiry
    
    def is_expired(self) -> bool:
        """Check if the cache entry has expired"""
        return datetime.now() > self.expiry

class SteamAPI:
    """Handles communication with Steam API"""
    
    BASE_URL = "https://api.steampowered.com"
    STORE_API_URL = "https://store.steampowered.com/api"
    COMMUNITY_URL = "https://steamcommunity.com"
    
    # Default Cache TTL in seconds - can be overridden in settings
    DEFAULT_CACHE_TTL = {
        "player_summary": 3600,  # 1 hour
        "owned_games": 3600 * 24,  # 24 hours
        "app_details": 3600 * 24 * 7,  # 1 week
        "current_players": 300,  # 5 minutes
        "player_bans": 3600 * 12,  # 12 hours
        "player_level": 3600 * 24,  # 24 hours
        "recent_games": 3600 * 3,  # 3 hours
        "friend_list": 3600 * 6,  # 6 hours
    }
    
    # Default rate limit settings (will be overridden by settings)
    DEFAULT_RATE_LIMITS = {
        "default": {"tokens_per_second": 1.0, "max_tokens": 10},
        "IPlayerService": {"tokens_per_second": 0.5, "max_tokens": 5},
        "ISteamUser": {"tokens_per_second": 0.5, "max_tokens": 5},
        "store": {"tokens_per_second": 0.25, "max_tokens": 3}
    }
    
    def __init__(self):
        # Using property to access the encrypted API key
        self._api_key = None
        self.rate_limit_wait = 1  # Initial wait time (seconds)
        self.max_retries = 3
        self.cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
        self.cache = {}
        
        # Cache statistics
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "writes": 0,
            "errors": 0,
            "last_cleanup": datetime.now(),
            "by_type": {}  # Will track hits/misses by cache type
        }
        
        # Initialize cache settings from the global settings
        self.use_compression = settings.cache_settings.get("use_compression", True)
        self.cache_enabled = settings.cache_settings.get("enabled", True)
        self.max_memory_entries = settings.cache_settings.get("max_memory_entries", 1000)
        self.cache_cleanup_interval = settings.cache_settings.get("cleanup_interval", 3600)
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        # Set up a session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,  # 0.5, 1, 2, 4... seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Initialize rate limiters based on settings
        self._init_rate_limiters()
        
        # Initialize cache TTLs from settings or use defaults
        self.cache_ttl = self._init_cache_ttl()
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Schedule periodic cache maintenance
        if self.cache_enabled:
            self._schedule_cache_maintenance()
    
    def _init_cache_ttl(self) -> Dict[str, int]:
        """Initialize cache TTL values from settings or use defaults"""
        cache_ttl = self.DEFAULT_CACHE_TTL.copy()
        
        # Override from settings if available
        if hasattr(settings, 'cache_ttl') and isinstance(settings.cache_ttl, dict):
            for cache_type, ttl in settings.cache_ttl.items():
                if ttl > 0:  # Only use valid TTL values
                    cache_ttl[cache_type] = ttl
                    logger.debug(f"Using custom TTL for {cache_type}: {ttl} seconds")
        
        return cache_ttl
    
    def _schedule_cache_maintenance(self):
        """Schedule periodic cache maintenance tasks using a background thread"""
        def maintenance_worker():
            while True:
                try:
                    # Sleep for the configured interval
                    time.sleep(self.cache_cleanup_interval)
                    
                    # Check if cache is still enabled
                    if not self.cache_enabled:
                        logger.debug("Cache disabled, stopping maintenance thread")
                        break
                        
                    removed = self._remove_expired_cache_entries()
                    self._update_cache_stats()
                    self._manage_memory_cache_size()
                    
                    logger.debug(f"Cache maintenance completed: removed {removed} expired entries")
                except Exception as e:
                    logger.error(f"Error during cache maintenance: {e}")
        
        # Start maintenance thread
        maintenance_thread = threading.Thread(
            target=maintenance_worker,
            name="CacheMaintenance",
            daemon=True
        )
        maintenance_thread.start()
        logger.debug("Started cache maintenance thread")
    
    def _init_rate_limiters(self):
        """Initialize rate limiters from settings"""
        # Start with default rate limits
        rate_limits = self.DEFAULT_RATE_LIMITS.copy()
        
        # Override with settings if rate limiting is enabled
        if settings.rate_limiting.get("enabled", True):
            # Update rates from settings
            if "default_rate" in settings.rate_limiting:
                rate_limits["default"]["tokens_per_second"] = settings.rate_limiting["default_rate"]
            
            if "player_service_rate" in settings.rate_limiting:
                rate_limits["IPlayerService"]["tokens_per_second"] = settings.rate_limiting["player_service_rate"]
            
            if "user_service_rate" in settings.rate_limiting:
                rate_limits["ISteamUser"]["tokens_per_second"] = settings.rate_limiting["user_service_rate"]
            
            if "store_api_rate" in settings.rate_limiting:
                rate_limits["store"]["tokens_per_second"] = settings.rate_limiting["store_api_rate"]
        
        # Create rate limiters
        self.rate_limiters = {
            endpoint: RateLimiter(**config) 
            for endpoint, config in rate_limits.items()
        }
        
        # Set adaptive flag based on settings
        self.adaptive_rate_limiting = settings.rate_limiting.get("adaptive", True)
        
        logger.info("Rate limiters initialized from settings")
    
    def _get_rate_limiter(self, endpoint: str) -> RateLimiter:
        """Get the appropriate rate limiter for an endpoint"""
        # Extract the service name from the endpoint (e.g., "ISteamUser/GetPlayerSummaries/v0002/" -> "ISteamUser")
        service = endpoint.split('/')[0] if '/' in endpoint else endpoint
        
        # Return the specific rate limiter if it exists, otherwise use default
        return self.rate_limiters.get(service, self.rate_limiters["default"])
    
    @property
    def api_key(self):
        """Get the API key, fetching from settings if needed"""
        if not self._api_key:
            self._api_key = settings.api_key
        return self._api_key
    
    @api_key.setter
    def api_key(self, value):
        """Set the API key"""
        self._api_key = value
    
    def set_api_key(self, api_key: str) -> None:
        """Set the Steam API key and store it securely in settings"""
        if not api_key:
            logger.warning("Attempted to set empty API key")
            return
            
        self.api_key = api_key
        settings.api_key = api_key
        settings.save_settings()
        logger.info("API key updated and encrypted in settings")
    
    def test_api_key(self) -> bool:
        """Test if the API key is valid by making a simple request"""
        if not self.api_key:
            logger.warning("No API key to test")
            return False
        
        try:
            # Try to get Dota 2 player count - a simple API call that should work with any valid key
            endpoint = "ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
            params = {'appid': 570}  # Dota 2 app ID
            
            data = self._make_request(endpoint, params)
            
            if data and 'response' in data and 'player_count' in data['response']:
                logger.info("API key test successful")
                return True
            else:
                logger.warning("API key test failed: unexpected response format")
                return False
        except Exception as e:
            logger.error(f"API key test failed: {e}")
            return False
    
    def _get_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate a unique cache key for a request"""
        # Sort params to ensure consistent keys regardless of parameter order
        sorted_params = sorted(
            [(k, v) for k, v in params.items() if k != 'key'],  # Exclude API key from cache key
            key=lambda x: x[0]
        )
        
        # Create a hash of the parameters instead of using them directly
        # This avoids issues with illegal filename characters
        param_str = json.dumps(sorted_params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        
        # Clean endpoint name for use in filename
        safe_endpoint = endpoint.replace('/', '_').replace('\\', '_')
        
        return f"{safe_endpoint}_{param_hash}"
    
    def _get_from_cache(self, cache_type: str, cache_key: str) -> Optional[Any]:
        """Get data from cache if available and not expired"""
        # Initialize cache stats for this type if needed
        with self.lock:
            if cache_type not in self.cache_stats["by_type"]:
                self.cache_stats["by_type"][cache_type] = {"hits": 0, "misses": 0, "writes": 0}
        
        # Check memory cache first
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if not entry.is_expired():
                logger.debug(f"Memory cache hit for {cache_key}")
                with self.lock:
                    self.cache_stats["hits"] += 1
                    self.cache_stats["by_type"][cache_type]["hits"] += 1
                return entry.data
            else:
                # Remove expired entry
                del self.cache[cache_key]
        
        # Try file cache next
        # Ensure the cache key is safe for use as a filename
        safe_key = cache_key.replace('/', '_').replace('\\', '_')
        safe_key = ''.join(c for c in safe_key if c.isalnum() or c in '_-')
        
        # Check both compressed and uncompressed cache files
        cache_file = os.path.join(self.cache_dir, f"{cache_type}_{safe_key}.json")
        compressed_cache_file = os.path.join(self.cache_dir, f"{cache_type}_{safe_key}.json.gz")
        
        # Try compressed file first if it exists
        if self.use_compression and os.path.exists(compressed_cache_file):
            try:
                with gzip.open(compressed_cache_file, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
                    if datetime.fromisoformat(data['expiry']) > datetime.now():
                        # Add to memory cache
                        self.cache[cache_key] = CacheEntry(
                            data['data'],
                            datetime.fromisoformat(data['expiry'])
                        )
                        logger.debug(f"Compressed file cache hit for {cache_key}")
                        with self.lock:
                            self.cache_stats["hits"] += 1
                            self.cache_stats["by_type"][cache_type]["hits"] += 1
                        return data['data']
                    else:
                        # Remove expired cache file
                        try:
                            os.remove(compressed_cache_file)
                        except:
                            pass
            except Exception as e:
                logger.error(f"Error reading compressed cache file: {e}")
                # Remove corrupted cache file
                try:
                    os.remove(compressed_cache_file)
                except:
                    pass
                with self.lock:
                    self.cache_stats["errors"] += 1
        
        # Try uncompressed file if compressed file doesn't exist or failed
        elif os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    if datetime.fromisoformat(data['expiry']) > datetime.now():
                        # Add to memory cache
                        self.cache[cache_key] = CacheEntry(
                            data['data'],
                            datetime.fromisoformat(data['expiry'])
                        )
                        logger.debug(f"File cache hit for {cache_key}")
                        with self.lock:
                            self.cache_stats["hits"] += 1
                            self.cache_stats["by_type"][cache_type]["hits"] += 1
                        return data['data']
                    else:
                        # Remove expired cache file
                        try:
                            os.remove(cache_file)
                        except:
                            pass
            except Exception as e:
                logger.error(f"Error reading cache file: {e}")
                # Remove corrupted cache file
                try:
                    os.remove(cache_file)
                except:
                    pass
                with self.lock:
                    self.cache_stats["errors"] += 1
        
        # Cache miss
        with self.lock:
            self.cache_stats["misses"] += 1
            self.cache_stats["by_type"][cache_type]["misses"] += 1
        return None
    
    def _save_to_cache(self, cache_type: str, cache_key: str, data: Any) -> None:
        """Save data to cache with appropriate expiration"""
        # Get TTL for this cache type
        ttl = self.cache_ttl.get(cache_type, 3600)  # Default to 1 hour if not specified
        expiry = datetime.now() + timedelta(seconds=ttl)
        
        # Save to memory cache
        self.cache[cache_key] = CacheEntry(data, expiry)
        
        # Check if we need to evict items from memory cache
        self._manage_memory_cache_size()
        
        # Track cache write
        with self.lock:
            self.cache_stats["writes"] += 1
            if cache_type in self.cache_stats["by_type"]:
                self.cache_stats["by_type"][cache_type]["writes"] += 1
            else:
                self.cache_stats["by_type"][cache_type] = {"hits": 0, "misses": 0, "writes": 1}
        
        # Save to file cache
        # Ensure cache directory exists
        if not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
            except Exception as e:
                logger.error(f"Failed to create cache directory: {e}")
                return
        
        # Ensure the cache key is safe for use as a filename
        safe_key = cache_key.replace('/', '_').replace('\\', '_')
        safe_key = ''.join(c for c in safe_key if c.isalnum() or c in '_-')
        
        cache_data = {
            'data': data,
            'expiry': expiry.isoformat(),
            'created_at': datetime.now().isoformat(),
            'cache_type': cache_type
        }
        
        if self.use_compression:
            # Save as compressed file
            cache_file = os.path.join(self.cache_dir, f"{cache_type}_{safe_key}.json.gz")
            try:
                with gzip.open(cache_file, 'wt', encoding='utf-8') as f:
                    json.dump(cache_data, f)
            except Exception as e:
                logger.error(f"Error writing to compressed cache file: {e}")
                with self.lock:
                    self.cache_stats["errors"] += 1
        else:
            # Save as uncompressed file
            cache_file = os.path.join(self.cache_dir, f"{cache_type}_{safe_key}.json")
            try:
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)
            except Exception as e:
                logger.error(f"Error writing to cache file: {e}")
                with self.lock:
                    self.cache_stats["errors"] += 1
    
    def _manage_memory_cache_size(self) -> None:
        """Manage memory cache size to prevent memory leaks"""
        # If cache size is below limit, no action needed
        if len(self.cache) <= self.max_memory_entries:
            return
            
        with self.lock:
            # We need to evict some items
            items_to_evict = len(self.cache) - self.max_memory_entries + 10  # Remove a few extra to avoid frequent evictions
            
            # Sort by expiry time - remove oldest expiring items first
            items = [(k, v.expiry) for k, v in self.cache.items()]
            items.sort(key=lambda x: x[1])  # Sort by expiry date
            
            # Remove the items closest to expiry
            keys_to_remove = [k for k, _ in items[:items_to_evict]]
            for key in keys_to_remove:
                del self.cache[key]
                
            logger.debug(f"Memory cache size management: evicted {len(keys_to_remove)} items")
    
    def _remove_expired_cache_entries(self) -> int:
        """Remove expired entries from cache and return count of removed entries"""
        removed_count = 0
        
        # Remove from memory cache
        now = datetime.now()
        with self.lock:
            expired_keys = [k for k, v in self.cache.items() if v.is_expired()]
            for key in expired_keys:
                del self.cache[key]
                removed_count += 1
        
        # Remove from file cache
        if os.path.exists(self.cache_dir):
            for file in os.listdir(self.cache_dir):
                if not file.endswith('.json') and not file.endswith('.json.gz'):
                    continue
                    
                try:
                    file_path = os.path.join(self.cache_dir, file)
                    
                    # Handle compressed files
                    if file.endswith('.json.gz'):
                        with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            
                    if datetime.fromisoformat(data['expiry']) < now:
                        os.remove(file_path)
                        removed_count += 1
                except Exception as e:
                    logger.error(f"Error checking/removing cache file {file}: {e}")
                    try:
                        os.remove(os.path.join(self.cache_dir, file))
                        removed_count += 1
                    except:
                        pass
        
        if removed_count > 0:
            logger.info(f"Cache maintenance: removed {removed_count} expired entries")
        return removed_count
    
    def _update_cache_stats(self) -> None:
        """Update cache statistics including hit rate and cache efficiency"""
        with self.lock:
            total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
            hit_rate = (self.cache_stats["hits"] / total_requests) * 100 if total_requests > 0 else 0
            
            # Calculate efficiency by type
            type_stats = {}
            for cache_type, stats in self.cache_stats["by_type"].items():
                type_requests = stats["hits"] + stats["misses"]
                type_hit_rate = (stats["hits"] / type_requests) * 100 if type_requests > 0 else 0
                type_stats[cache_type] = {
                    "hit_rate": f"{type_hit_rate:.1f}%",
                    "requests": type_requests,
                    "hits": stats["hits"],
                    "misses": stats["misses"]
                }
            
            # Update last cleanup time
            self.cache_stats["last_cleanup"] = datetime.now()
            self.cache_stats["hit_rate"] = f"{hit_rate:.1f}%"
            self.cache_stats["efficiency_by_type"] = type_stats
            
            logger.info(f"Cache stats: {hit_rate:.1f}% hit rate ({self.cache_stats['hits']} hits, {self.cache_stats['misses']} misses)")
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 0, use_cache: bool = True, cache_type: Optional[str] = None) -> Any:
        """Make a request to the Steam API with proxy, caching and rate limit handling"""
        if not self.api_key:
            logger.error("API key not set")
            raise SteamAPIError("API key not set")
            
        if params is None:
            params = {}
        
        # Don't modify the original params
        request_params = params.copy()
            
        # Add API key to params
        request_params['key'] = self.api_key
        
        # Check cache if enabled
        if use_cache and cache_type and self.cache_enabled:
            cache_key = self._get_cache_key(endpoint, params)
            cached_data = self._get_from_cache(cache_type, cache_key)
            if cached_data:
                return cached_data
        
        # Apply rate limiting only if enabled in settings
        if settings.rate_limiting.get("enabled", True):
            rate_limiter = self._get_rate_limiter(endpoint)
            wait_time = rate_limiter.consume()
            
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds before request to {endpoint}")
                time.sleep(wait_time)
        
        # Get proxy if enabled
        session = self.session
        if proxy_manager.enabled:
            # Use proxy manager's connection pooled session instead of just the proxy config
            session = proxy_manager.get_session()
        
        try:
            response = session.get(
                f"{self.BASE_URL}/{endpoint}",
                params=request_params,
                timeout=10
            )
            
            # Handle rate limiting not caught by the retry adapter
            if response.status_code == 429:
                logger.warning(f"Rate limited on {endpoint}. Status code: 429")
                
                # Mark proxy as rate limited and rotate to a new one
                if proxy_manager.enabled:
                    new_proxy = proxy_manager.mark_proxy_rate_limited()
                    if new_proxy:
                        logger.info(f"Rotated to a new proxy after rate limit")
                        # Get a new session with the rotated proxy
                        session = proxy_manager.get_session()
                
                # Apply exponential backoff
                wait_time = self.rate_limit_wait * (2 ** retry_count)  # Exponential backoff
                logger.warning(f"Rate limited. Waiting {wait_time} seconds before retry")
                time.sleep(wait_time)
                
                # Adjust rate limiter to be more conservative if adaptive rate limiting is enabled
                if self.adaptive_rate_limiting:
                    with self.lock:
                        rate_limiter = self._get_rate_limiter(endpoint)
                        current_rate = rate_limiter.tokens_per_second
                        # Reduce rate by 25%
                        new_rate = max(0.1, current_rate * 0.75)
                        logger.info(f"Adjusting {endpoint} rate limit from {current_rate} to {new_rate} requests/sec")
                        rate_limiter.tokens_per_second = new_rate
                        
                        # Update settings if this is a known endpoint
                        if endpoint.startswith("ISteamUser"):
                            if "user_api_rate" in settings.rate_limiting:
                                settings.rate_limiting["user_api_rate"] = new_rate
                                settings.save_settings()
                        elif endpoint.startswith("ISteamApps"):
                            if "apps_api_rate" in settings.rate_limiting:
                                settings.rate_limiting["apps_api_rate"] = new_rate
                                settings.save_settings()
                
                return self._make_request(endpoint, params, retry_count + 1, use_cache, cache_type)
            
            # Handle other errors
            if response.status_code != 200:
                logger.warning(f"API request failed with status {response.status_code}: {response.text}")
                
                # If we get a 403 or 401, try rotating proxy as it might be IP banned
                if response.status_code in (401, 403, 503) and proxy_manager.enabled:
                    logger.warning(f"Got {response.status_code} status, rotating proxy")
                    proxy_manager.mark_proxy_failure()
                    new_proxy = proxy_manager.rotate_proxy()
                    if new_proxy:
                        # Get a new session with the rotated proxy
                        session = proxy_manager.get_session()
                
                if retry_count < self.max_retries:
                    wait_time = self.rate_limit_wait * (2 ** retry_count)
                    logger.warning(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    return self._make_request(endpoint, params, retry_count + 1, use_cache, cache_type)
                else:
                    raise SteamAPIError(f"API request failed with status {response.status_code}")
            
            # Mark proxy as successful
            if proxy_manager.enabled:
                proxy_manager.mark_proxy_success()
            
            data = response.json()
            
            # Save to cache if enabled
            if use_cache and cache_type and data:
                cache_key = self._get_cache_key(endpoint, params)
                self._save_to_cache(cache_type, cache_key, data)
                
            return data
            
        except requests.RequestException as e:
            logger.warning(f"Request error: {e}")
            
            # Mark proxy as failed and rotate
            if proxy_manager.enabled:
                proxy_manager.mark_proxy_failure()
                new_proxy = proxy_manager.rotate_proxy()
                if new_proxy:
                    logger.info(f"Rotated to a new proxy after connection error")
                    # Get a new session with the rotated proxy for next attempt
                
            if retry_count < self.max_retries:
                wait_time = self.rate_limit_wait * (2 ** retry_count)
                logger.warning(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                return self._make_request(endpoint, params, retry_count + 1, use_cache, cache_type)
            else:
                raise SteamAPIError(f"Request failed after {self.max_retries} retries: {e}")
    
    def _make_store_request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 0, use_cache: bool = True, cache_type: Optional[str] = None) -> Any:
        """Make a request to the Steam Store API"""
        if params is None:
            params = {}
        
        # Check cache if enabled
        if use_cache and cache_type and self.cache_enabled:
            cache_key = self._get_cache_key(endpoint, params)
            cached_data = self._get_from_cache(cache_type, cache_key)
            if cached_data:
                return cached_data
                
        # Apply rate limiting for store API if enabled in settings
        if settings.rate_limiting.get("enabled", True):
            rate_limiter = self._get_rate_limiter("store")
            wait_time = rate_limiter.consume()
            
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds before store request to {endpoint}")
                time.sleep(wait_time)
        
        # Get proxy session if enabled
        session = self.session
        if proxy_manager.enabled:
            # Use proxy manager's connection pooled session
            session = proxy_manager.get_session()
        
        try:
            response = session.get(
                f"{self.STORE_API_URL}/{endpoint}",
                params=params,
                timeout=10
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                logger.warning(f"Rate limited on store API {endpoint}. Status code: 429")
                
                # Mark proxy as rate limited and rotate to a new one
                if proxy_manager.enabled:
                    new_proxy = proxy_manager.mark_proxy_rate_limited()
                    if new_proxy:
                        logger.info(f"Rotated to a new proxy after store API rate limit")
                        # Get a new session with the rotated proxy
                        session = proxy_manager.get_session()
                
                # Apply exponential backoff
                wait_time = self.rate_limit_wait * (2 ** retry_count)
                logger.warning(f"Rate limited by Steam Store. Waiting {wait_time} seconds before retry")
                time.sleep(wait_time)
                
                # Adjust store rate limiter to be more conservative if adaptive rate limiting is enabled
                if self.adaptive_rate_limiting:
                    with self.lock:
                        current_rate = self.rate_limiters["store"].tokens_per_second
                        # Reduce rate by 25%
                        new_rate = max(0.1, current_rate * 0.75)
                        logger.info(f"Adjusting store rate limit from {current_rate} to {new_rate} requests/sec")
                        self.rate_limiters["store"].tokens_per_second = new_rate
                        
                        # Update settings
                        if "store_api_rate" in settings.rate_limiting:
                            settings.rate_limiting["store_api_rate"] = new_rate
                            settings.save_settings()
                
                return self._make_store_request(endpoint, params, retry_count + 1, use_cache, cache_type)
            
            # Handle other errors
            if response.status_code != 200:
                # If we get a 403 or 401, try rotating proxy as it might be IP banned
                if response.status_code in (401, 403, 503) and proxy_manager.enabled:
                    logger.warning(f"Got {response.status_code} status from store API, rotating proxy")
                    proxy_manager.mark_proxy_failure()
                    new_proxy = proxy_manager.rotate_proxy()
                    if new_proxy:
                        # Get a new session with the rotated proxy
                        session = proxy_manager.get_session()
                
                if retry_count < self.max_retries:
                    wait_time = self.rate_limit_wait * (2 ** retry_count)
                    logger.warning(f"Store API request failed with status {response.status_code}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    return self._make_store_request(endpoint, params, retry_count + 1, use_cache, cache_type)
                else:
                    raise SteamAPIError(f"Store API request failed with status {response.status_code}")
            
            # Mark proxy as successful
            if proxy_manager.enabled:
                proxy_manager.mark_proxy_success()
            
            data = response.json()
            
            # Save to cache if enabled
            if use_cache and cache_type and data:
                cache_key = self._get_cache_key(endpoint, params)
                self._save_to_cache(cache_type, cache_key, data)
                
            return data
            
        except requests.RequestException as e:
            logger.warning(f"Store API request error: {e}")
            
            # Mark proxy as failed and rotate
            if proxy_manager.enabled:
                proxy_manager.mark_proxy_failure()
                new_proxy = proxy_manager.rotate_proxy()
                if new_proxy:
                    logger.info(f"Rotated to a new proxy after store API connection error")
                    # New session will be fetched on retry
            
            if retry_count < self.max_retries:
                wait_time = self.rate_limit_wait * (2 ** retry_count)
                logger.warning(f"Store API request failed: {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                return self._make_store_request(endpoint, params, retry_count + 1, use_cache, cache_type)
            else:
                raise SteamAPIError(f"Store API request failed after {self.max_retries} retries: {e}")
    
    def get_player_summaries(self, steam_id: Union[str, int]) -> Optional[Dict]:
        """Get player profile information"""
        endpoint = "ISteamUser/GetPlayerSummaries/v0002/"
        params = {'steamids': steam_id}
        
        data = self._make_request(endpoint, params, use_cache=True, cache_type="player_summary")
        
        if not data or 'response' not in data or 'players' not in data['response']:
            return None
            
        players = data['response']['players']
        return players[0] if players else None
    
    def get_owned_games(self, steam_id: Union[str, int]) -> List[Dict]:
        """Get a list of games owned by the player"""
        endpoint = "IPlayerService/GetOwnedGames/v0001/"
        params = {
            'steamid': steam_id,
            'include_appinfo': 1,
            'include_played_free_games': 0
        }
        
        data = self._make_request(endpoint, params, use_cache=True, cache_type="owned_games")
        
        if not data or 'response' not in data:
            return []
            
        return data['response'].get('games', [])
    
    def get_app_details(self, app_id: Union[str, int]) -> Optional[Dict]:
        """Get detailed information about a game"""
        params = {'appids': app_id}
        
        data = self._make_store_request('appdetails', params, use_cache=True, cache_type="app_details")
        
        if data and str(app_id) in data and data[str(app_id)]['success']:
            return data[str(app_id)]['data']
        return None
    
    def is_game_paid(self, app_id: Union[str, int]) -> bool:
        """Check if a game is a paid game (not free-to-play)"""
        app_details = self.get_app_details(app_id)
        if not app_details:
            return False
            
        # Check if the game is free-to-play
        return not app_details.get('is_free', True)
    
    def get_paid_games(self, steam_id: Union[str, int]) -> List[Dict]:
        """Get a list of paid games owned by the player"""
        games = self.get_owned_games(steam_id)
        paid_games = []
        
        for game in games:
            app_id = game['appid']
            if self.is_game_paid(app_id):
                paid_games.append(game)
                
        return paid_games
    
    def get_user_bans(self, steam_id: Union[str, int]) -> Optional[Dict]:
        """Get account ban information"""
        endpoint = "ISteamUser/GetPlayerBans/v1/"
        params = {'steamids': steam_id}
        
        data = self._make_request(endpoint, params, use_cache=True, cache_type="player_bans")
        
        if not data or 'players' not in data:
            return None
            
        players = data['players']
        return players[0] if players else None
    
    def get_user_level(self, steam_id: Union[str, int]) -> Optional[int]:
        """Get user's Steam level"""
        endpoint = "IPlayerService/GetSteamLevel/v1/"
        params = {'steamid': steam_id}
        
        data = self._make_request(endpoint, params, use_cache=True, cache_type="player_level")
        
        if not data or 'response' not in data:
            return None
            
        return data['response'].get('player_level')
    
    def get_recently_played_games(self, steam_id: Union[str, int], count: int = 10) -> List[Dict]:
        """Get recently played games for a user"""
        endpoint = "IPlayerService/GetRecentlyPlayedGames/v1/"
        params = {
            'steamid': steam_id,
            'count': count
        }
        
        data = self._make_request(endpoint, params, use_cache=True, cache_type="recent_games")
        
        if not data or 'response' not in data:
            return []
            
        return data['response'].get('games', [])
    
    def get_friend_list(self, steam_id: Union[str, int]) -> List[Dict]:
        """Get a user's friend list"""
        endpoint = "ISteamUser/GetFriendList/v1/"
        params = {
            'steamid': steam_id,
            'relationship': 'friend'
        }
        
        data = self._make_request(endpoint, params, use_cache=True, cache_type="friend_list")
        
        if not data or 'friendslist' not in data or 'friends' not in data['friendslist']:
            return []
            
        return data['friendslist']['friends']
    
    def clear_cache(self, cache_types: Optional[List[str]] = None) -> None:
        """
        Clear cached data, optionally for specific cache types only
        
        Args:
            cache_types: List of cache types to clear, or None to clear all
        """
        with self.lock:
            if cache_types is None:
                # Clear all cache
                self.cache = {}
                
                # Clear all file cache
                if os.path.exists(self.cache_dir):
                    for file in os.listdir(self.cache_dir):
                        if file.endswith('.json') or file.endswith('.json.gz'):
                            try:
                                os.remove(os.path.join(self.cache_dir, file))
                            except Exception as e:
                                logger.error(f"Failed to delete cache file {file}: {e}")
                
                logger.info("All API cache cleared")
            else:
                # Clear specific cache types only
                # First clear from memory cache
                keys_to_delete = []
                for key, entry in self.cache.items():
                    for cache_type in cache_types:
                        if key.startswith(f"{cache_type}_"):
                            keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    del self.cache[key]
                
                # Then clear from file cache
                if os.path.exists(self.cache_dir):
                    for file in os.listdir(self.cache_dir):
                        if not (file.endswith('.json') or file.endswith('.json.gz')):
                            continue
                            
                        for cache_type in cache_types:
                            if file.startswith(f"{cache_type}_"):
                                try:
                                    os.remove(os.path.join(self.cache_dir, file))
                                except Exception as e:
                                    logger.error(f"Failed to delete cache file {file}: {e}")
                
                logger.info(f"Cleared cache for types: {', '.join(cache_types)}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the cache performance"""
        with self.lock:
            # Make a copy of the stats to avoid thread safety issues
            stats = self.cache_stats.copy()
            
            # Add current cache size information
            stats["memory_cache_entries"] = len(self.cache)
            
            # Count file cache entries and size
            file_count = 0
            file_size_bytes = 0
            if os.path.exists(self.cache_dir):
                for file in os.listdir(self.cache_dir):
                    if file.endswith('.json') or file.endswith('.json.gz'):
                        file_count += 1
                        try:
                            file_size_bytes += os.path.getsize(os.path.join(self.cache_dir, file))
                        except:
                            pass
            
            stats["file_cache_entries"] = file_count
            stats["file_cache_size_mb"] = round(file_size_bytes / (1024 * 1024), 2)
            
            return stats
    
    def update_cache_settings(self, settings_dict: Dict[str, Any]) -> bool:
        """
        Update cache settings
        
        Args:
            settings_dict: Dictionary with cache settings to update
                {
                    "use_compression": bool,
                    "ttl": {
                        "cache_type": seconds,
                        ...
                    }
                }
        
        Returns:
            bool: True if settings were updated successfully
        """
        try:
            if "use_compression" in settings_dict:
                self.use_compression = bool(settings_dict["use_compression"])
            
            if "ttl" in settings_dict and isinstance(settings_dict["ttl"], dict):
                for cache_type, ttl in settings_dict["ttl"].items():
                    if isinstance(ttl, (int, float)) and ttl > 0:
                        self.cache_ttl[cache_type] = int(ttl)
                        logger.debug(f"Updated TTL for {cache_type}: {ttl} seconds")
            
            # Save to app settings if needed
            if hasattr(settings, 'cache_ttl'):
                settings.cache_ttl = self.cache_ttl
                settings.save_settings()
            
            logger.info("Cache settings updated")
            return True
        except Exception as e:
            logger.error(f"Failed to update cache settings: {e}")
            return False

    def invalidate_cache_for_steam_id(self, steam_id: str) -> int:
        """
        Invalidate all cached data related to a specific Steam ID
        
        Args:
            steam_id: Steam ID to invalidate cache for
            
        Returns:
            int: Number of cache entries invalidated
        """
        invalidated = 0
        
        # Prepare steam_id for cache key search
        steam_id_str = str(steam_id)
        
        # Invalidate memory cache
        with self.lock:
            keys_to_delete = []
            for key in self.cache.keys():
                if steam_id_str in key:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache[key]
                invalidated += 1
        
        # Invalidate file cache
        if os.path.exists(self.cache_dir):
            # We'll need to read each file to check if it contains the steam_id
            for file in os.listdir(self.cache_dir):
                if not (file.endswith('.json') or file.endswith('.json.gz')):
                    continue
                
                if steam_id_str in file:
                    # Fast path: filename contains the steam_id
                    try:
                        os.remove(os.path.join(self.cache_dir, file))
                        invalidated += 1
                    except Exception as e:
                        logger.error(f"Failed to delete cache file {file}: {e}")
        
        if invalidated > 0:
            logger.info(f"Invalidated {invalidated} cache entries for Steam ID {steam_id}")
        
        return invalidated

    def refresh_rate_limiters(self) -> None:
        """Refresh rate limiters from settings"""
        self._init_rate_limiters()
        logger.info("Rate limiters refreshed from settings")
        
    def update_rate_limits(self, rate_limits: Dict[str, float]) -> None:
        """
        Update rate limits for specific endpoints
        
        Args:
            rate_limits: Dictionary mapping endpoint names to rates (requests per second)
                         Example: {"default": 1.0, "IPlayerService": 0.5}
        """
        if not rate_limits:
            return
            
        settings_update = {}
        
        with self.lock:
            # Update rate limiters in memory
            for endpoint, rate in rate_limits.items():
                if endpoint in self.rate_limiters:
                    logger.info(f"Updating rate limit for {endpoint} to {rate} requests/second")
                    self.rate_limiters[endpoint].tokens_per_second = rate
                    
                    # Map to settings keys
                    if endpoint == "default":
                        settings_update["default_rate"] = rate
                    elif endpoint == "IPlayerService":
                        settings_update["player_service_rate"] = rate
                    elif endpoint == "ISteamUser":
                        settings_update["user_service_rate"] = rate
                    elif endpoint == "store":
                        settings_update["store_api_rate"] = rate
        
        # Update settings if any changes were made
        if settings_update:
            settings.update_rate_limits(settings_update)
            
    def get_current_rate_limits(self) -> Dict[str, float]:
        """Get the current rate limits for all endpoints"""
        return {
            endpoint: limiter.tokens_per_second
            for endpoint, limiter in self.rate_limiters.items()
        }

# Global Steam API instance
steam_api = SteamAPI()
