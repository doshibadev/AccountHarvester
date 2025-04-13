import random
import time
import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
from utils.logger import logger
from config.settings import settings

class ProxyManager:
    """Manages proxy connections and rotation"""
    
    def __init__(self):
        self.proxies = []
        self.current_proxy = None
        self.enabled = False
        self.failed_proxies = set()
        self.proxy_performance = {}  # Format: {proxy: {'success': count, 'fail': count, 'last_use': timestamp}}
        self.rate_limited_proxies = {}  # Format: {proxy: cooling_until_timestamp}
        self.rate_limit_cooldown = 60  # Seconds to cool down a rate-limited proxy
        
        # Connection pool settings
        self.pool_connections = 50  # Base number of connection pools to keep in memory
        self.pool_maxsize = 100  # Maximum number of connections to save in the pool
        self.max_retries = 3  # Maximum number of retries for connection errors
        
        # Dictionary to store sessions for each proxy
        self.proxy_sessions = {}
    
    def load_proxies(self, proxy_list=None):
        """Load proxies from settings or a provided list"""
        if proxy_list:
            self.proxies = proxy_list
        else:
            self.proxies = settings.proxies
        
        self.enabled = len(self.proxies) > 0 and settings.enable_proxies
        
        # Initialize connection pools for each proxy
        if self.enabled:
            self._initialize_connection_pools()
            logger.info(f"Loaded {len(self.proxies)} proxies with connection pooling")
        
        return self.enabled
    
    def _initialize_connection_pools(self):
        """Initialize connection pools for all proxies"""
        # Clear existing sessions
        for session in self.proxy_sessions.values():
            session.close()
        
        self.proxy_sessions = {}
        
        # Create a session with connection pooling for each proxy
        for proxy in self.proxies:
            self.proxy_sessions[proxy] = self._create_pooled_session(proxy)
            
        logger.debug(f"Initialized connection pools for {len(self.proxy_sessions)} proxies")
    
    def _create_pooled_session(self, proxy_str):
        """Create a requests session with connection pooling for a specific proxy"""
        session = requests.Session()
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=0.5,  # 0.5, 1, 2, 4... seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        
        # Create adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.pool_connections,
            pool_maxsize=self.pool_maxsize
        )
        
        # Mount the adapter to both http and https
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set the proxy for this session
        proxy_dict = self.format_proxy(proxy_str)
        if proxy_dict:
            session.proxies = proxy_dict
        
        return session
    
    def get_proxy(self):
        """Get the next proxy in rotation"""
        if not self.enabled or not self.proxies:
            return None
        
        # Remove any proxies from rate limit cooldown that have expired
        now = time.time()
        expired_rate_limits = [p for p, cooling_until in self.rate_limited_proxies.items() 
                              if cooling_until <= now]
        for proxy in expired_rate_limits:
            self.rate_limited_proxies.pop(proxy, None)
            logger.debug(f"Proxy {proxy} rate limit cooldown expired, making available again")
        
        # Filter out failed proxies and rate-limited proxies
        available_proxies = [p for p in self.proxies 
                           if p not in self.failed_proxies 
                           and p not in self.rate_limited_proxies]
        
        if not available_proxies:
            # If all proxies are rate-limited or failed
            if self.rate_limited_proxies:
                # If we have rate-limited proxies, use the one with the soonest expiry
                soonest_proxy = min(self.rate_limited_proxies.items(), key=lambda x: x[1])[0]
                logger.warning(f"All proxies are rate-limited or failed. Using {soonest_proxy} despite rate limit")
                self.current_proxy = soonest_proxy
                return self.format_proxy(self.current_proxy)
            elif self.failed_proxies:
                # Reset failed proxies if all have failed
                logger.warning("All proxies have failed, resetting failed list")
                self.failed_proxies.clear()
                available_proxies = [p for p in self.proxies if p not in self.rate_limited_proxies]
                if not available_proxies:
                    available_proxies = self.proxies  # Use all if still none available
        
        # Choose proxy with highest success rate or random if no performance data
        if self.proxy_performance:
            def score_proxy(p):
                if p not in self.proxy_performance:
                    return 0
                stats = self.proxy_performance[p]
                success = stats.get('success', 0)
                fail = stats.get('fail', 0)
                if success + fail == 0:
                    return 0
                return success / (success + fail)
            
            available_proxies.sort(key=score_proxy, reverse=True)
            self.current_proxy = available_proxies[0]
        else:
            self.current_proxy = random.choice(available_proxies)
        
        return self.format_proxy(self.current_proxy)
    
    def get_session(self):
        """Get a session with the current proxy configured"""
        if not self.enabled or not self.current_proxy:
            return requests.Session()
            
        # If the proxy has a session, return it
        if self.current_proxy in self.proxy_sessions:
            return self.proxy_sessions[self.current_proxy]
        
        # If not, create a new one on the fly
        session = self._create_pooled_session(self.current_proxy)
        self.proxy_sessions[self.current_proxy] = session
        return session
        
    def mark_proxy_rate_limited(self):
        """Mark the current proxy as rate limited"""
        if not self.current_proxy or not self.enabled:
            return
        
        now = time.time()
        cooling_until = now + self.rate_limit_cooldown
        self.rate_limited_proxies[self.current_proxy] = cooling_until
        
        # Also mark in performance metrics
        if self.current_proxy not in self.proxy_performance:
            self.proxy_performance[self.current_proxy] = {'success': 0, 'fail': 0, 'rate_limits': 0}
        
        self.proxy_performance[self.current_proxy]['rate_limits'] = self.proxy_performance[self.current_proxy].get('rate_limits', 0) + 1
        self.proxy_performance[self.current_proxy]['last_use'] = now
        
        logger.warning(f"Proxy {self.current_proxy} marked as rate limited for {self.rate_limit_cooldown} seconds")
        
        # Return a new proxy for immediate use
        return self.rotate_proxy()
    
    def rotate_proxy(self):
        """Rotate to a new proxy and return it"""
        if not self.enabled or len(self.proxies) <= 1:
            return None
        
        # Save current proxy to check later
        old_proxy = self.current_proxy
        
        # Force get a different proxy
        exclude = {old_proxy}
        available_proxies = [p for p in self.proxies 
                          if p not in exclude 
                          and p not in self.failed_proxies 
                          and p not in self.rate_limited_proxies]
        
        if not available_proxies:
            logger.warning("No alternate proxies available for rotation")
            return None
        
        # Choose a new proxy
        if self.proxy_performance:
            def score_proxy(p):
                if p not in self.proxy_performance:
                    return 0
                stats = self.proxy_performance[p]
                success = stats.get('success', 0)
                fail = stats.get('fail', 0)
                rate_limits = stats.get('rate_limits', 0)
                if success + fail == 0:
                    return 0
                # Prioritize proxies with fewer rate limits
                rate_limit_penalty = rate_limits * 0.1
                return (success / (success + fail)) - rate_limit_penalty
            
            available_proxies.sort(key=score_proxy, reverse=True)
            self.current_proxy = available_proxies[0]
        else:
            self.current_proxy = random.choice(available_proxies)
        
        logger.info(f"Rotated proxy from {old_proxy} to {self.current_proxy}")
        return self.format_proxy(self.current_proxy)
    
    def format_proxy(self, proxy_str):
        """Format proxy string to requests format"""
        if not proxy_str:
            return None
            
        parts = proxy_str.split(':')
        if len(parts) >= 4:  # With authentication
            ip, port, username, password = parts[0:4]
            auth_str = f"{username}:{password}"
            proxy_dict = {
                'http': f'http://{auth_str}@{ip}:{port}',
                'https': f'http://{auth_str}@{ip}:{port}'
            }
        else:  # Without authentication
            ip, port = parts[0:2]
            proxy_dict = {
                'http': f'http://{ip}:{port}',
                'https': f'http://{ip}:{port}'
            }
        
        return proxy_dict
    
    def mark_proxy_success(self):
        """Mark the current proxy as successful"""
        if not self.current_proxy:
            return
            
        if self.current_proxy not in self.proxy_performance:
            self.proxy_performance[self.current_proxy] = {'success': 0, 'fail': 0, 'rate_limits': 0}
            
        self.proxy_performance[self.current_proxy]['success'] = self.proxy_performance[self.current_proxy].get('success', 0) + 1
        self.proxy_performance[self.current_proxy]['last_use'] = time.time()
    
    def mark_proxy_failure(self):
        """Mark the current proxy as failed"""
        if not self.current_proxy:
            return
            
        if self.current_proxy not in self.proxy_performance:
            self.proxy_performance[self.current_proxy] = {'success': 0, 'fail': 0, 'rate_limits': 0}
            
        self.proxy_performance[self.current_proxy]['fail'] = self.proxy_performance[self.current_proxy].get('fail', 0) + 1
        self.proxy_performance[self.current_proxy]['last_use'] = time.time()
        
        # Add to failed list if fail rate is high
        fail = self.proxy_performance[self.current_proxy]['fail']
        success = self.proxy_performance[self.current_proxy]['success']
        
        if fail > 3 and success / (success + fail) < 0.3:
            self.failed_proxies.add(self.current_proxy)
            logger.warning(f"Proxy {self.current_proxy} added to failed list")
    
    def test_proxy(self, proxy_str):
        """Test if a proxy is working"""
        try:
            # Create a temporary session for testing
            session = self._create_pooled_session(proxy_str)
            response = session.get('https://api.ipify.org', timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Proxy test failed: {e}")
            return False
        finally:
            # Clean up the test session
            if 'session' in locals():
                session.close()
    
    def test_all_proxies(self):
        """Test all proxies and remove non-working ones"""
        working_proxies = []
        
        for proxy in self.proxies:
            if self.test_proxy(proxy):
                working_proxies.append(proxy)
                logger.info(f"Proxy {proxy} is working")
            else:
                logger.warning(f"Proxy {proxy} is not working")
        
        self.proxies = working_proxies
        
        # Reinitialize connection pools with working proxies
        if working_proxies:
            self._initialize_connection_pools()
            
        return len(working_proxies)
    
    def get_proxy_status(self):
        """Get detailed status of all proxies"""
        now = time.time()
        status = {
            'total': len(self.proxies),
            'failed': len(self.failed_proxies),
            'rate_limited': len(self.rate_limited_proxies),
            'available': len([p for p in self.proxies if p not in self.failed_proxies and p not in self.rate_limited_proxies]),
            'current': self.current_proxy,
            'enabled': self.enabled,
            'connection_pooling': {
                'pool_connections': self.pool_connections,
                'pool_maxsize': self.pool_maxsize,
                'active_sessions': len(self.proxy_sessions)
            },
            'details': {}
        }
        
        for proxy in self.proxies:
            proxy_status = {
                'failed': proxy in self.failed_proxies,
                'rate_limited': proxy in self.rate_limited_proxies,
                'has_session': proxy in self.proxy_sessions,
                'performance': self.proxy_performance.get(proxy, {'success': 0, 'fail': 0, 'rate_limits': 0})
            }
            
            if proxy in self.rate_limited_proxies:
                cooling_until = self.rate_limited_proxies[proxy]
                proxy_status['cooldown_remaining'] = max(0, cooling_until - now)
            
            status['details'][proxy] = proxy_status
            
        return status
    
    def cleanup(self):
        """Clean up resources when shutting down"""
        for session in self.proxy_sessions.values():
            session.close()
        
        self.proxy_sessions.clear()
        logger.info("Proxy connection pools cleaned up")

# Global proxy manager instance
proxy_manager = ProxyManager()
