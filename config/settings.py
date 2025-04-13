import json
import os
from pathlib import Path
from utils.logger import logger
from utils.crypto import encrypt, decrypt
from utils.input_validation import validate_proxy, validate_thread_count, validate_file_path
from typing import Dict, Any

class Settings:
    def __init__(self):
        # Default settings
        self._api_key = ""  # Private attribute for the encrypted API key
        self._thread_count = 5  # Default thread count
        self.proxies = []
        self.active_proxy = None
        self.enable_proxies = False
        self.proxy_file = ""
        
        # Rate limiting settings
        self.rate_limiting = {
            "enabled": True,
            "default_rate": 1.0,        # Requests per second
            "player_service_rate": 0.5, # Requests per second for player service
            "user_service_rate": 0.5,   # Requests per second for user service
            "store_api_rate": 0.25,     # Requests per second for store API
            "adaptive": True            # Automatically adjust rates based on 429 responses
        }
        
        # Auto-retry settings
        self.auto_retry = {
            "enabled": True,            # Enable/disable auto-retry
            "max_retries": 3,           # Maximum number of retry attempts
            "initial_backoff": 1.0,     # Initial backoff time in seconds
            "backoff_factor": 2.0,      # Multiplier for backoff on each retry
            "jitter": 0.1,              # Random jitter factor to add to backoff (0.0-1.0)
            "retry_network_errors": True # Retry network-related errors automatically
        }
        
        # Cache settings
        self.cache_settings = {
            "enabled": True,            # Enable/disable caching 
            "use_compression": True,    # Use compression for cache files
            "max_memory_entries": 1000, # Maximum number of entries to keep in memory
            "cleanup_interval": 3600    # How often to run cache cleanup (seconds)
        }
        
        # Cache TTL settings (in seconds)
        self.cache_ttl = {
            "player_summary": 3600,     # 1 hour
            "owned_games": 86400,       # 24 hours
            "app_details": 604800,      # 1 week
            "current_players": 300,     # 5 minutes
            "player_bans": 43200,       # 12 hours
            "player_level": 86400,      # 24 hours
            "recent_games": 10800,      # 3 hours
            "friend_list": 21600        # 6 hours
        }
        
        self.settings_file = Path("config/app_settings.json")
        self.load_settings()
    
    @property
    def api_key(self):
        """Getter for API key - decrypts the stored value"""
        return decrypt(self._api_key)
    
    @api_key.setter
    def api_key(self, value):
        """Setter for API key - encrypts the value before storing"""
        self._api_key = encrypt(value)
    
    @property
    def thread_count(self):
        """Getter for thread count"""
        return self._thread_count
    
    @thread_count.setter
    def thread_count(self, value):
        """Setter for thread count with validation"""
        is_valid, error_msg, validated_count = validate_thread_count(value)
        if is_valid:
            self._thread_count = validated_count
        else:
            logger.warning(f"Invalid thread count ({value}): {error_msg}. Using {validated_count} instead.")
            self._thread_count = validated_count
    
    def load_settings(self):
        """Load settings from the config file if it exists"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    data = json.load(f)
                
                # Handle api_key specially for encryption
                if 'api_key' in data:
                    # Check if already encrypted
                    if data['api_key'].startswith('gAAAAA'):  # Fernet encrypted data starts with this
                        self._api_key = data['api_key']
                    else:
                        # Encrypt the API key if it wasn't already
                        logger.info("Encrypting API key in settings")
                        self.api_key = data['api_key']
                
                # Handle thread count with validation
                if 'thread_count' in data:
                    self.thread_count = data['thread_count']
                
                # Update other attributes from loaded settings
                for key, value in data.items():
                    if key not in ('api_key', 'thread_count') and hasattr(self, key):
                        setattr(self, key, value)
                        
                # Validate proxies
                self._validate_proxies()
                
                # Ensure rate limiting settings exist with defaults if missing
                if 'rate_limiting' not in data:
                    logger.info("Rate limiting settings not found, using defaults")
                elif isinstance(data['rate_limiting'], dict):
                    # Only update existing keys to ensure backward compatibility
                    for key, value in data['rate_limiting'].items():
                        if key in self.rate_limiting:
                            self.rate_limiting[key] = value
                
                # Ensure auto-retry settings exist with defaults if missing
                if 'auto_retry' not in data:
                    logger.info("Auto-retry settings not found, using defaults")
                elif isinstance(data['auto_retry'], dict):
                    # Only update existing keys to ensure backward compatibility
                    for key, value in data['auto_retry'].items():
                        if key in self.auto_retry:
                            self.auto_retry[key] = value
                
                # Ensure cache settings exist with defaults if missing
                if 'cache_settings' not in data:
                    logger.info("Cache settings not found, using defaults")
                elif isinstance(data['cache_settings'], dict):
                    # Only update existing keys to ensure backward compatibility
                    for key, value in data['cache_settings'].items():
                        if key in self.cache_settings:
                            self.cache_settings[key] = value
                
                # Ensure cache TTL settings exist with defaults if missing
                if 'cache_ttl' not in data:
                    logger.info("Cache TTL settings not found, using defaults")
                elif isinstance(data['cache_ttl'], dict):
                    # Only update existing keys to ensure backward compatibility
                    for key, value in data['cache_ttl'].items():
                        self.cache_ttl[key] = value
                
                logger.info("Settings loaded successfully")
            except Exception as e:
                logger.error(f"Error loading settings: {str(e)}", exc_info=True)
                print(f"Error loading settings: {e}")
    
    def _validate_proxies(self):
        """Validate loaded proxies and remove invalid ones"""
        valid_proxies = []
        for proxy in self.proxies:
            is_valid, _ = validate_proxy(proxy)
            if is_valid:
                valid_proxies.append(proxy)
            else:
                logger.warning(f"Removing invalid proxy: {proxy}")
        
        if len(valid_proxies) != len(self.proxies):
            logger.info(f"Removed {len(self.proxies) - len(valid_proxies)} invalid proxies")
            self.proxies = valid_proxies
    
    def save_settings(self):
        """Save current settings to the config file"""
        # Create directory if it doesn't exist
        os.makedirs(self.settings_file.parent, exist_ok=True)
        
        # Save only serializable attributes
        settings_dict = {
            'api_key': self._api_key,  # Store the encrypted API key
            'thread_count': self._thread_count,
            'proxies': self.proxies,
            'enable_proxies': self.enable_proxies,
            'proxy_file': self.proxy_file,
            'rate_limiting': self.rate_limiting,
            'auto_retry': self.auto_retry,
            'cache_settings': self.cache_settings,
            'cache_ttl': self.cache_ttl
        }
        
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings_dict, f, indent=4)
            logger.info("Settings saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {str(e)}", exc_info=True)
            print(f"Error saving settings: {e}")
            return False
    
    def load_proxies_from_file(self, file_path):
        """Load proxies from a file, one proxy per line in format ip:port or ip:port:user:pass"""
        try:
            # Validate file path first
            is_valid, error_msg = validate_file_path(file_path, must_exist=True)
            if not is_valid:
                logger.error(f"Invalid proxy file path: {error_msg}")
                return False
            
            with open(file_path, 'r') as f:
                new_proxies = []
                for line in f:
                    proxy = line.strip()
                    if proxy and not proxy.startswith('#'):
                        is_valid, error_msg = validate_proxy(proxy)
                        if is_valid:
                            new_proxies.append(proxy)
                        else:
                            logger.warning(f"Ignoring invalid proxy ({error_msg}): {proxy}")
            
            self.proxies = new_proxies
            self.proxy_file = file_path
            logger.info(f"Loaded {len(self.proxies)} proxies from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading proxies: {str(e)}", exc_info=True)
            print(f"Error loading proxies: {e}")
            return False
            
    def update_rate_limits(self, rate_limits):
        """Update rate limiting settings"""
        if not isinstance(rate_limits, dict):
            logger.error("Invalid rate limits format")
            return False
            
        # Update only valid keys
        for key, value in rate_limits.items():
            if key in self.rate_limiting:
                # Validate numeric rates to ensure they're positive
                if key.endswith('_rate') and not isinstance(value, (int, float)):
                    logger.warning(f"Invalid rate value for {key}: {value}. Must be a number.")
                    continue
                if key.endswith('_rate') and value <= 0:
                    logger.warning(f"Invalid rate value for {key}: {value}. Must be positive.")
                    continue
                    
                self.rate_limiting[key] = value
                logger.debug(f"Updated rate limit setting: {key} = {value}")
        
        self.save_settings()
        return True

    def update_auto_retry_settings(self, auto_retry_settings):
        """Update auto-retry settings"""
        if not isinstance(auto_retry_settings, dict):
            logger.error("Invalid auto-retry settings format")
            return False
            
        # Update only valid keys
        for key, value in auto_retry_settings.items():
            if key in self.auto_retry:
                # Validate numeric values to ensure they're positive
                if key in ['max_retries', 'initial_backoff', 'backoff_factor'] and not isinstance(value, (int, float)):
                    logger.warning(f"Invalid value for {key}: {value}. Must be a number.")
                    continue
                if key in ['max_retries', 'initial_backoff', 'backoff_factor'] and value <= 0:
                    logger.warning(f"Invalid value for {key}: {value}. Must be positive.")
                    continue
                # Validate jitter is between 0 and 1
                if key == 'jitter' and (value < 0 or value > 1):
                    logger.warning(f"Invalid jitter value: {value}. Must be between 0 and 1.")
                    continue
                    
                self.auto_retry[key] = value
                logger.debug(f"Updated auto-retry setting: {key} = {value}")
        
        self.save_settings()
        return True

    def update_cache_settings(self, cache_settings: Dict[str, Any]) -> bool:
        """Update cache settings"""
        if not isinstance(cache_settings, dict):
            logger.error("Invalid cache settings format")
            return False
            
        # Update specific cache settings
        if "enabled" in cache_settings:
            self.cache_settings["enabled"] = bool(cache_settings["enabled"])
            
        if "use_compression" in cache_settings:
            self.cache_settings["use_compression"] = bool(cache_settings["use_compression"])
            
        if "max_memory_entries" in cache_settings:
            try:
                value = int(cache_settings["max_memory_entries"])
                if value > 0:
                    self.cache_settings["max_memory_entries"] = value
            except (ValueError, TypeError):
                logger.warning(f"Invalid max_memory_entries value: {cache_settings['max_memory_entries']}")
                
        if "cleanup_interval" in cache_settings:
            try:
                value = int(cache_settings["cleanup_interval"])
                if value > 0:
                    self.cache_settings["cleanup_interval"] = value
            except (ValueError, TypeError):
                logger.warning(f"Invalid cleanup_interval value: {cache_settings['cleanup_interval']}")
        
        # Update TTL settings if provided
        if "ttl" in cache_settings and isinstance(cache_settings["ttl"], dict):
            for cache_type, ttl in cache_settings["ttl"].items():
                try:
                    value = int(ttl)
                    if value > 0:
                        self.cache_ttl[cache_type] = value
                        logger.debug(f"Updated cache TTL for {cache_type}: {value}s")
                except (ValueError, TypeError):
                    logger.warning(f"Invalid TTL value for {cache_type}: {ttl}")
        
        self.save_settings()
        return True

# Create a global settings instance
settings = Settings()
