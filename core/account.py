import time
import enum
from steam.client import SteamClient
from steam.enums import EResult
from steam.enums.emsg import EMsg
from utils.logger import logger
from utils.input_validation import validate_credentials, sanitize_input
from core.proxy_manager import proxy_manager
from core.steam_api import steam_api
import threading
import concurrent.futures
from queue import Queue, Empty
import gc
import sys
import signal
import random

class AccountStatus(enum.Enum):
    UNKNOWN = "Unknown"
    VALID = "Valid"
    ERROR = "Error"
    STEAMGUARD = "SteamGuard"

# Map Steam error codes to human-readable messages
STEAM_ERROR_MESSAGES = {
    EResult.InvalidPassword: "Invalid password",
    EResult.AccountNotFound: "Account not found",
    EResult.InvalidName: "Invalid account name",
    EResult.AccountDisabled: "Account is disabled",
    EResult.AccountLogonDenied: "Account requires SteamGuard email code",
    EResult.AccountLoginDeniedNeedTwoFactor: "Account requires two-factor authentication",
    EResult.PasswordRequiredToKickSession: "Another session exists for this account",
    EResult.RateLimitExceeded: "Rate limit exceeded - too many login attempts",
    EResult.AccountLockedDown: "Account is locked",
    EResult.IPBanned: "IP address is banned",
    EResult.InvalidLoginAuthCode: "Invalid SteamGuard code",
    EResult.ExpiredLoginAuthCode: "Expired SteamGuard code",
    EResult.ServiceUnavailable: "Steam service unavailable (account may be valid)",
    EResult.Timeout: "Connection timed out",
    EResult.TryAnotherCM: "Steam servers busy - try another connection",
    EResult.TwoFactorCodeMismatch: "Incorrect two-factor code",
    EResult.LimitExceeded: "Limit exceeded for login attempts"
}

def get_error_message(result_code):
    """Convert a Steam EResult code to a human-readable error message"""
    if result_code in STEAM_ERROR_MESSAGES:
        return STEAM_ERROR_MESSAGES[result_code]
    return f"Unknown error ({result_code.name}, code {result_code.value})"

class SteamAccount:
    """Represents a Steam account with login and verification functionality"""
    
    def __init__(self, username, password):
        # Sanitize inputs to prevent XSS and similar attacks
        self.username = sanitize_input(username)
        self.password = password  # Don't sanitize password to preserve special characters
        self.status = AccountStatus.UNKNOWN
        self.error_message = None
        self.error_code = None
        self.steam_id = None
        self.games = []
        self.login_result = None
        # Create the client with a specific connection timeout
        self.steam_client = None
        # Retry tracking
        self.retry_count = 0
        self.max_retries = 3
    
    @classmethod
    def from_credentials_line(cls, credentials_line):
        """Create an account from a credentials line (username:password)"""
        # Use the validation utility to validate and parse credentials
        is_valid, error_msg, parsed_creds = validate_credentials(credentials_line)
        if not is_valid:
            logger.error(f"Invalid credentials format: {error_msg}")
            return None
        
        username, password = parsed_creds
        return cls(username, password)
    
    def _create_client(self):
        """Create a fresh SteamClient instance"""
        # Ensure any previous client is cleaned up
        if hasattr(self, 'steam_client') and self.steam_client:
            self.cleanup()
        # Create a new client
        self.steam_client = SteamClient()
        # Set a low timeout for operations to prevent blocking
        self.steam_client.cm_servers.timeout = 5.0
        return self.steam_client
        
    def check_account(self, max_retries=3, initial_backoff=1.0, backoff_factor=2.0, jitter=0.1):
        """
        Check if the account is valid by attempting to log in with auto-retry and exponential backoff
        
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            initial_backoff: Initial backoff time in seconds (default: 1.0)
            backoff_factor: Multiplier for backoff on each retry (default: 2.0)
            jitter: Random jitter factor to add to backoff (default: 0.1)
            
        Returns:
            AccountStatus indicating the result of the check
        """
        # Store retry settings
        self.max_retries = max_retries
        self.retry_count = 0
        backoff_time = initial_backoff
        
        # Set up proxy management if enabled
        current_proxy = None
        if proxy_manager.enabled:
            current_proxy = proxy_manager.get_proxy()
            logger.debug(f"Using proxy for account {self.username}")
        
        # Loop for retries
        while self.retry_count <= max_retries:
            # Create a fresh client for each attempt
            self.steam_client = SteamClient()
            
            # Apply proxy settings if enabled
            if current_proxy and proxy_manager.enabled:
                try:
                    # SteamClient doesn't directly support proxies, so we need to configure the underlying session
                    # This is implementation-specific and may need adjustment based on the steam library used
                    if hasattr(self.steam_client, 'session'):
                        self.steam_client.session.proxies = current_proxy
                    logger.debug(f"Applied proxy settings to Steam client for {self.username}")
                except Exception as e:
                    logger.warning(f"Failed to apply proxy settings to Steam client: {e}")
            
            try:
                # If this is a retry, log it
                if self.retry_count > 0:
                    logger.info(f"Retry attempt {self.retry_count}/{max_retries} for account {self.username}")
                
                # Connect to Steam
                logger.info(f"Connecting to Steam for account {self.username}")
                connected = self.steam_client.connect()
                
                if not connected:
                    error_msg = "Failed to connect to Steam servers"
                    logger.error(f"{error_msg} for account {self.username}")
                    
                    # If connection failed and we're using proxies, try rotating
                    if current_proxy and proxy_manager.enabled:
                        proxy_manager.mark_proxy_failure()
                        new_proxy = proxy_manager.rotate_proxy()
                        if new_proxy:
                            logger.info(f"Rotated to a new proxy after connection failure for {self.username}")
                            current_proxy = new_proxy
                    
                    # If we have retries left, try again
                    if self.retry_count < max_retries:
                        self.retry_count += 1
                        # Calculate backoff with jitter
                        jitter_amount = random.uniform(-jitter, jitter) * backoff_time
                        sleep_time = backoff_time + jitter_amount
                        logger.info(f"Backing off for {sleep_time:.2f} seconds before retry")
                        time.sleep(sleep_time)
                        # Increase backoff for next retry
                        backoff_time *= backoff_factor
                        continue
                    
                    # No more retries
                    self.status = AccountStatus.ERROR
                    self.error_message = error_msg
                    self.error_code = "CONNECTION_FAILED"
                    return self.status
                
                # Attempt to log in
                logger.info(f"Attempting to log in with account {self.username}")
                self.login_result = self.steam_client.login(
                    username=self.username,
                    password=self.password,
                    auth_code=None,  # No 2FA code for initial attempt
                    two_factor_code=None  # No 2FA code for initial attempt
                )
                
                # Store the error code for reference
                self.error_code = self.login_result
                
                # Check the login result
                if self.login_result == EResult.OK:
                    # Successfully logged in - mark proxy as successful
                    if current_proxy and proxy_manager.enabled:
                        proxy_manager.mark_proxy_success()
                        
                    self.status = AccountStatus.VALID
                    self.steam_id = self.steam_client.steam_id
                    logger.info(f"Account {self.username} is valid (Steam ID: {self.steam_id})")
                    return self.status
                    
                elif self.login_result in (EResult.AccountLogonDenied, EResult.AccountLoginDeniedNeedTwoFactor):
                    # Account requires SteamGuard - no retry needed
                    # Still mark the proxy as successful since the request worked
                    if current_proxy and proxy_manager.enabled:
                        proxy_manager.mark_proxy_success()
                        
                    self.status = AccountStatus.STEAMGUARD
                    self.error_message = get_error_message(self.login_result)
                    logger.info(f"Account {self.username} requires SteamGuard: {self.error_message}")
                    return self.status
                    
                elif self.login_result == EResult.ServiceUnavailable:
                    # Error code 50 - account is valid but service unavailable
                    # This is expected sometimes, mark proxy as successful
                    if current_proxy and proxy_manager.enabled:
                        proxy_manager.mark_proxy_success()
                        
                    self.status = AccountStatus.VALID
                    self.error_message = "Error Code 50: Service Unavailable. The account is valid but Steam servers are busy."
                    logger.info(f"Account {self.username} returned Error 50 (valid but unavailable)")
                    return self.status
                
                # Determine if error is retryable
                retryable_errors = [
                    EResult.RateLimitExceeded,
                    EResult.ServiceUnavailable,
                    EResult.Timeout,
                    EResult.TryAnotherCM,
                    EResult.LimitExceeded
                ]
                
                # Handle rate limiting specially - rotate proxies if available
                if self.login_result == EResult.RateLimitExceeded and current_proxy and proxy_manager.enabled:
                    logger.warning(f"Rate limit detected for {self.username}, marking proxy as rate limited")
                    new_proxy = proxy_manager.mark_proxy_rate_limited()
                    if new_proxy:
                        logger.info(f"Rotated to a new proxy after rate limit for {self.username}")
                        current_proxy = new_proxy
                
                if self.login_result in retryable_errors and self.retry_count < max_retries:
                    # Retryable error and we have retries left
                    self.retry_count += 1
                    error_msg = get_error_message(self.login_result)
                    logger.warning(f"Retryable error for {self.username}: {error_msg}. Retry {self.retry_count}/{max_retries}")
                    
                    # Calculate backoff with jitter
                    jitter_amount = random.uniform(-jitter, jitter) * backoff_time
                    sleep_time = backoff_time + jitter_amount
                    logger.info(f"Backing off for {sleep_time:.2f} seconds before retry")
                    time.sleep(sleep_time)
                    # Increase backoff for next retry
                    backoff_time *= backoff_factor
                    continue
                
                # Any other error or no more retries - probably invalid credentials
                self.status = AccountStatus.ERROR
                self.error_message = get_error_message(self.login_result)
                logger.error(f"Account {self.username} login failed: {self.login_result.name} - {self.error_message}")
                return self.status
                
            except Exception as e:
                # Mark proxy as failed if connection error
                if current_proxy and proxy_manager.enabled and (
                    "timeout" in str(e).lower() or 
                    "connection" in str(e).lower() or
                    "reset" in str(e).lower() or
                    "refused" in str(e).lower()
                ):
                    proxy_manager.mark_proxy_failure()
                    new_proxy = proxy_manager.rotate_proxy()
                    if new_proxy:
                        logger.info(f"Rotated to a new proxy after connection error for {self.username}")
                        current_proxy = new_proxy
                
                # Determine if we should retry on exception
                should_retry = (
                    "timeout" in str(e).lower() or 
                    "connection" in str(e).lower() or
                    "reset" in str(e).lower() or
                    "refused" in str(e).lower()
                )
                
                if should_retry and self.retry_count < max_retries:
                    self.retry_count += 1
                    logger.warning(f"Exception checking account {self.username}, retrying ({self.retry_count}/{max_retries}): {e}")
                    
                    # Calculate backoff with jitter
                    jitter_amount = random.uniform(-jitter, jitter) * backoff_time
                    sleep_time = backoff_time + jitter_amount
                    logger.info(f"Backing off for {sleep_time:.2f} seconds before retry")
                    time.sleep(sleep_time)
                    # Increase backoff for next retry
                    backoff_time *= backoff_factor
                    continue
                
                # Log and handle any exception after retries exhausted
                self.status = AccountStatus.ERROR
                self.error_message = str(e)
                self.error_code = "EXCEPTION"
                logger.error(f"Error checking account {self.username} after {self.retry_count} retries: {e}")
                return self.status
                
            finally:
                # Always try to clean up
                try:
                    if self.steam_client and self.steam_client.connected:
                        self.steam_client.logout()
                        self.steam_client.disconnect()
                except Exception as e:
                    logger.debug(f"Error during client cleanup for {self.username}: {e}")
                
                # Remove reference to client
                self.steam_client = None
        
        # We should never get here, but just in case
        self.status = AccountStatus.ERROR
        self.error_message = "All retry attempts failed"
        return self.status
    
    def get_steam_id(self):
        """Get the Steam ID for this account"""
        return self.steam_id
    
    def fetch_owned_games(self):
        """Fetch the list of games owned by this account (requires API key)"""
        if self.status != AccountStatus.VALID or not self.steam_id:
            logger.warning(f"Cannot fetch games for invalid account {self.username}")
            return []
            
        try:
            games = steam_api.get_owned_games(self.steam_id)
            paid_games = [g for g in games if steam_api.is_game_paid(g['appid'])]
            self.games = paid_games
            logger.info(f"Found {len(paid_games)} paid games for account {self.username}")
            return paid_games
        except Exception as e:
            logger.error(f"Error fetching games for account {self.username}: {e}")
            return []
    
    def to_dict(self):
        """Convert account data to a dictionary for export"""
        return {
            'username': self.username,
            'password': self.password,
            'status': self.status.value,
            'steam_id': str(self.steam_id) if self.steam_id else None,
            'error': self.error_message,
            'error_code': str(self.error_code) if self.error_code else None,
            'games': [g['name'] for g in self.games] if self.games else []
        }
    
    def to_csv_row(self):
        """Format account data as a CSV row"""
        game_count = len(self.games) if self.games else 0
        return [
            self.username,
            self.password,
            self.status.value,
            str(self.steam_id) if self.steam_id else '',
            self.error_message if self.error_message else '',
            str(game_count)
        ]
    
    def cleanup(self):
        """Clean up resources used by this account"""
        logger.debug(f"Cleaning up resources for account {self.username}")
        if not hasattr(self, 'steam_client') or not self.steam_client:
            return
        
        try:
            # First try graceful cleanup with very short timeouts
            client = self.steam_client
            self.steam_client = None  # Prevent circular references
            
            # Attempt to log out and disconnect with minimal timeout
            try:
                if client.connected:
                    try:
                        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                        future = executor.submit(client.logout)
                        future.result(timeout=1)
                    except:
                        pass
                    
                    try:
                        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                        future = executor.submit(client.disconnect)
                        future.result(timeout=1)
                    except:
                        pass
            except:
                pass
                
            # Let the garbage collector handle any remaining references
            client = None
        except:
            pass
        
        # Force garbage collection to clean up gevent resources
        gc.collect()

class AccountChecker:
    """Manages the process of checking multiple accounts"""
    
    def __init__(self):
        self.accounts = []
        self.results = {
            AccountStatus.VALID: [],
            AccountStatus.ERROR: [],
            AccountStatus.STEAMGUARD: []
        }
        self._is_running = False
        self._should_stop = False
        self._results_lock = threading.RLock()  # Add a lock for thread-safe results access
    
    def add_account(self, account):
        """Add an account to be checked"""
        if isinstance(account, SteamAccount):
            self.accounts.append(account)
        elif isinstance(account, str):
            acc = SteamAccount.from_credentials_line(account)
            if acc:
                self.accounts.append(acc)
    
    def add_accounts_from_file(self, file_path):
        """Load accounts from a file, one per line in format username:password"""
        valid_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Validate credentials before creating account
                    is_valid, error_msg, parsed_creds = validate_credentials(line)
                    if is_valid:
                        username, password = parsed_creds
                        account = SteamAccount(username, password)
                        self.accounts.append(account)
                        valid_count += 1
                    else:
                        # Log the error but hide the full credentials
                        sanitized = line.split(':', 1)[0] + ':******' if ':' in line else line
                        logger.warning(f"Skipping invalid credential line ({error_msg}): {sanitized}")
            
            return valid_count
        except Exception as e:
            logger.error(f"Error loading accounts from file: {e}", exc_info=True)
            return 0
    
    def check_account(self, account):
        """Check a single account"""
        try:
            # Get auto-retry settings from config
            from config.settings import settings
            
            # Check the account with auto-retry if enabled
            if settings.auto_retry["enabled"]:
                status = account.check_account(
                    max_retries=settings.auto_retry["max_retries"],
                    initial_backoff=settings.auto_retry["initial_backoff"],
                    backoff_factor=settings.auto_retry["backoff_factor"],
                    jitter=settings.auto_retry["jitter"]
                )
            else:
                # No auto-retry
                status = account.check_account(max_retries=0)
            
            # If valid, fetch games
            if status == AccountStatus.VALID and account.steam_id:
                account.fetch_owned_games()
            
            # Add to results
            self.results[status].append(account)
            
            return account
        except Exception as e:
            logger.error(f"Error checking account {account.username}: {e}")
            account.status = AccountStatus.ERROR
            account.error_message = str(e)
            self.results[AccountStatus.ERROR].append(account)
            return account
    
    def check_all_accounts(self, callback=None):
        """Check all accounts sequentially (no threading)"""
        if self._is_running:
            logger.warning("Account checking is already running")
            return self.results
        
        # Reset state
        self._is_running = True
        self._should_stop = False
        
        # Reset results
        self.results = {
            AccountStatus.VALID: [],
            AccountStatus.ERROR: [],
            AccountStatus.STEAMGUARD: []
        }
        
        try:
            total = len(self.accounts)
            logger.info(f"Starting to check {total} accounts (no threading)")
            
            # Process accounts one by one
            for i, account in enumerate(self.accounts):
                # Check if we should stop
                if self._should_stop:
                    logger.info("Account checking stopped by user")
                    break
                
                # Check the account
                logger.info(f"Checking account {i+1}/{total}: {account.username}")
                result = self.check_account(account)
                
                # Notify callback
                if callback:
                    callback(i+1, total, result)
                
                # Small delay to avoid hammering the Steam servers
                time.sleep(1)
            
            logger.info(f"Account checking completed. Results: {self.get_results_summary()}")
            
        except Exception as e:
            logger.error(f"Error during account checking: {e}")
        finally:
            self._is_running = False
        
        return self.results
    
    def check_all_accounts_threaded(self, callback=None, max_workers=None, timeout=30):
        """
        Check all accounts using thread pool for parallel processing
        
        Args:
            callback: Function to call with progress updates (current, total, account)
            max_workers: Maximum number of worker threads (None = use settings or CPU count)
            timeout: Maximum time in seconds for each account check
            
        Returns:
            Dictionary of results by account status
        """
        from utils.threading_utils import AdvancedThreadPool, TaskPriority
        
        if self._is_running:
            logger.warning("Account checking is already running")
            return self.results
        
        # Reset state
        self._is_running = True
        self._should_stop = False
        
        # Reset results
        self.results = {
            AccountStatus.VALID: [],
            AccountStatus.ERROR: [],
            AccountStatus.STEAMGUARD: []
        }
        
        try:
            total = len(self.accounts)
            
            # Determine thread count (use settings.thread_count or CPU count)
            if max_workers is None:
                from config.settings import settings
                max_workers = settings.thread_count
            
            logger.info(f"Starting to check {total} accounts with {max_workers} threads")
            
            # Initialize progress tracking
            progress_counter = {'current': 0, 'total': total}
            
            # Create a thread pool with the specified number of workers
            # We disable dynamic scaling to maintain exactly the specified thread count
            pool = AdvancedThreadPool(max_workers=max_workers, dynamic_scaling=False)
            
            # Get auto-retry settings from configuration
            from config.settings import settings
            auto_retry_enabled = settings.auto_retry["enabled"]
            max_retries = settings.auto_retry["max_retries"] if auto_retry_enabled else 0
            initial_backoff = settings.auto_retry["initial_backoff"]
            backoff_factor = settings.auto_retry["backoff_factor"]
            jitter = settings.auto_retry["jitter"]
            
            # Define safe task for checking a single account
            def check_single_account_task(account_index, account):
                # Early exit if stop requested
                if self._should_stop:
                    return None
                
                logger.info(f"Thread checking account {account_index+1}/{total}: {account.username}")
                
                try:
                    # Check the account
                    result = self.check_account(account)
                    
                    # Update progress
                    with self._results_lock:
                        progress_counter['current'] += 1
                        
                    # Notify callback
                    if callback:
                        callback(progress_counter['current'], total, result)
                    
                    return result
                except Exception as e:
                    logger.error(f"Error in thread checking account {account.username}: {e}")
                    # Ensure the account is marked as error even if check_account fails
                    account.status = AccountStatus.ERROR
                    account.error_message = str(e)
                    with self._results_lock:
                        self.results[AccountStatus.ERROR].append(account)
                        progress_counter['current'] += 1
                    
                    # Notify callback
                    if callback:
                        callback(progress_counter['current'], total, account)
                    
                    return account
            
            # Register a callback for task completion to ensure thread-safe results updating
            def on_task_complete(task):
                # Skip if result is None (task was aborted due to stop request)
                if task.result is None:
                    return
                
                # Skip if we're already stopping
                if self._should_stop:
                    return
                
            # Submit all account checks to the thread pool with appropriate timeout
            task_ids = []
            for i, account in enumerate(self.accounts):
                task_id = pool.submit(
                    check_single_account_task, 
                    i, account,
                    timeout=timeout,
                    max_retries=max_retries,              # Use configured retry count
                    initial_backoff=initial_backoff,      # Use configured initial backoff
                    backoff_factor=backoff_factor,        # Use configured backoff factor
                    jitter=jitter                         # Use configured jitter
                )
                task_ids.append(task_id)
            
            # Wait for all tasks to complete or until stop is requested
            while not pool.wait_for_completion(timeout=0.5):
                if self._should_stop:
                    logger.info("Account checking stopped by user")
                    pool.stop(wait=False)  # Non-blocking stop
                    break
            
            # Ensure thread pool is properly shut down
            pool.stop(wait=True, timeout=10)
            
            # Log completion
            logger.info(f"Account checking completed. Results: {self.get_results_summary()}")
        
        except Exception as e:
            logger.error(f"Error during threaded account checking: {e}")
        finally:
            self._is_running = False
        
        return self.results
    
    def stop_checking(self):
        """Stop the account checking process"""
        self._should_stop = True
        logger.info("Account checking stop requested")
    
    def get_results_summary(self):
        """Get a summary of the results"""
        return {
            'total': len(self.accounts),
            'valid': len(self.results[AccountStatus.VALID]),
            'error': len(self.results[AccountStatus.ERROR]),
            'steamguard': len(self.results[AccountStatus.STEAMGUARD])
        }
    
    def get_valid_accounts(self):
        """Get a list of valid accounts"""
        return self.results[AccountStatus.VALID]
    
    def get_error_accounts(self):
        """Get a list of error accounts"""
        return self.results[AccountStatus.ERROR]
    
    def get_steamguard_accounts(self):
        """Get a list of SteamGuard accounts"""
        return self.results[AccountStatus.STEAMGUARD]
