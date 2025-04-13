#!/usr/bin/env python3
import os
import sys
import argparse
import traceback
from utils.logger import logger
from config.settings import settings
from core.account import SteamAccount, AccountChecker, AccountStatus
from core.proxy_manager import proxy_manager
from core.exporter import exporter
from PyQt6.QtWidgets import QApplication
from ui.main_window import MainWindow
from utils.input_validation import (
    validate_api_key, validate_credentials, validate_file_path,
    validate_proxy, validate_thread_count, sanitize_input
)

def setup_argparse():
    """Set up command line arguments"""
    parser = argparse.ArgumentParser(description='AccountHarvester')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Check a single account
    check_parser = subparsers.add_parser('check', help='Check a single account')
    check_parser.add_argument('credentials', help='Account credentials in format username:password')
    
    # Check accounts from file
    file_parser = subparsers.add_parser('file', help='Check accounts from a file')
    file_parser.add_argument('file_path', help='Path to file with account credentials')
    file_parser.add_argument('--export', action='store_true', help='Export results to the specified format')
    file_parser.add_argument('--export-format', choices=['csv', 'json', 'txt', 'xml', 'yml'], default='csv',
                         help='Format for exported results (default: csv)')
    file_parser.add_argument('--no-threading', action='store_true', help='Disable multi-threading (use single thread)')
    
    # Proxy management
    proxy_parser = subparsers.add_parser('proxy', help='Proxy management')
    proxy_parser.add_argument('--list', action='store_true', help='List all active proxies')
    proxy_parser.add_argument('--add', help='Add a proxy in format ip:port or ip:port:user:pass')
    proxy_parser.add_argument('--remove', help='Remove a proxy by ID')
    proxy_parser.add_argument('--clear', action='store_true', help='Clear all proxies')
    
    # Other options
    parser.add_argument('--api-key', help='Steam API key for fetching account details')
    parser.add_argument('--gui', action='store_true', help='Launch the graphical user interface')
    
    # Rate limiting options
    rate_group = parser.add_argument_group('Rate Limiting Options')
    rate_group.add_argument('--rate-limit-enabled', type=lambda x: x.lower() == 'true', 
                         help='Enable or disable rate limiting (true/false)')
    rate_group.add_argument('--default-rate', type=float, help='Default rate limit in requests per second (e.g. 1.0)')
    rate_group.add_argument('--player-service-rate', type=float, help='Player service rate limit in requests per second (e.g. 0.5)')
    rate_group.add_argument('--user-service-rate', type=float, help='User service rate limit in requests per second (e.g. 0.5)')
    rate_group.add_argument('--store-api-rate', type=float, help='Store API rate limit in requests per second (e.g. 0.25)')
    rate_group.add_argument('--adaptive-rate-limiting', type=lambda x: x.lower() == 'true',
                         help='Enable or disable adaptive rate limiting (true/false)')
    
    # Auto-retry options
    retry_group = parser.add_argument_group('Auto-Retry Options')
    retry_group.add_argument('--auto-retry-enabled', type=lambda x: x.lower() == 'true',
                          help='Enable or disable automatic retry with exponential backoff (true/false)')
    retry_group.add_argument('--max-retries', type=int,
                          help='Maximum number of retry attempts for failed account checks (e.g. 3)')
    retry_group.add_argument('--initial-backoff', type=float,
                          help='Initial backoff time in seconds before the first retry (e.g. 1.0)')
    retry_group.add_argument('--backoff-factor', type=float,
                          help='Multiplier for backoff time on each subsequent retry (e.g. 2.0)')
    retry_group.add_argument('--jitter', type=float,
                          help='Random jitter factor to add to backoff (0.0-1.0)')
    
    return parser

def check_single_account(credentials):
    """Check a single account and display results"""
    try:
        # Validate credentials
        is_valid, error_msg, parsed_creds = validate_credentials(credentials)
        if not is_valid:
            logger.error(f"Invalid credentials: {error_msg}")
            print(f"Error: {error_msg}")
            return False
            
        # Create account using validated credentials
        username, password = parsed_creds
        account = SteamAccount(username, password)
        if not account:
            logger.error("Failed to create account object")
            return False
        
        logger.info(f"Checking account: {account.username}")
        status = account.check_account()
        
        print(f"\nAccount: {account.username}")
        print(f"Status: {status.value}")
        
        if status == AccountStatus.VALID:
            logger.info(f"Account {account.username} is valid")
            print("Account is valid!")
            if account.steam_id:
                print(f"Steam ID: {account.steam_id}")
            
            if settings.api_key:
                logger.info(f"Fetching owned games for {account.username}")
                print("\nFetching owned games...")
                try:
                    games = account.fetch_owned_games()
                    if games:
                        logger.info(f"Found {len(games)} games for {account.username}")
                        print(f"Found {len(games)} paid games:")
                        for i, game in enumerate(games[:10], 1):  # Show first 10 games
                            print(f"  {i}. {game['name']}")
                        if len(games) > 10:
                            print(f"  ... and {len(games) - 10} more")
                    else:
                        logger.warning(f"No games found for {account.username}")
                        print("No paid games found or error fetching games.")
                except Exception as e:
                    logger.error(f"Error fetching games: {str(e)}", exc_info=True)
                    print(f"Error fetching games: {str(e)}")
            else:
                logger.warning("No API key set, games cannot be fetched")
                print("\nNo API key set. Games cannot be fetched.")
        elif status == AccountStatus.STEAMGUARD:
            logger.info(f"Account {account.username} requires SteamGuard")
            print("Account requires SteamGuard authentication.")
            if account.error_message:
                print(f"Details: {account.error_message}")
        else:
            logger.warning(f"Login failed for {account.username}: {account.error_message}")
            print(f"Login failed: {account.error_message}")
            if account.error_code:
                if hasattr(account.error_code, 'name') and hasattr(account.error_code, 'value'):
                    error_code = f"{account.error_code.name} ({account.error_code.value})"
                    logger.warning(f"Error code: {error_code}")
                    print(f"Error Code: {error_code}")
                else:
                    logger.warning(f"Error code: {account.error_code}")
                    print(f"Error Code: {account.error_code}")
        
        return True
    except KeyboardInterrupt:
        logger.warning("Account check interrupted by user")
        print("\nOperation cancelled by user")
        return False
    except Exception as e:
        logger.error(f"Error checking account: {str(e)}", exc_info=True)
        print(f"Error checking account: {str(e)}")
        return False

def check_accounts_from_file(file_path, export=False, export_format='csv', threaded=True):
    """Check multiple accounts from a file"""
    # Validate file path
    is_valid, error_msg = validate_file_path(file_path, must_exist=True, allowed_extensions=['.txt'])
    if not is_valid:
        logger.error(f"Invalid file path: {error_msg}")
        print(f"Error: {error_msg}")
        return False
        
    checker = AccountChecker()
    
    try:
        logger.info(f"Loading accounts from {file_path}")
        num_accounts = checker.add_accounts_from_file(file_path)
        
        if num_accounts == 0:
            logger.error("No valid accounts found in the file")
            print("Error: No valid accounts found in the file")
            return False
        
        logger.info(f"Loaded {num_accounts} accounts")
        print(f"Loaded {num_accounts} accounts. Starting check...")
        
        # Progress callback
        def progress_callback(current, total, account):
            percent = int((current / total) * 100)
            status_text = account.status.value
            # Add error message for invalid accounts
            if account.status == AccountStatus.ERROR and account.error_message:
                status_text = f"{status_text} - {account.error_message}"
                logger.debug(f"Account {account.username}: {status_text}")
            print(f"Progress: {current}/{total} ({percent}%) - {account.username}: {status_text}")
        
        try:
            # Start checking
            print("Checking accounts...")
            if threaded:
                from config.settings import settings
                thread_count = settings.thread_count
                logger.info(f"Using threaded mode with {thread_count} threads")
                print(f"Using threaded mode with {thread_count} threads")
                results = checker.check_all_accounts_threaded(callback=progress_callback)
            else:
                logger.info("Using single-threaded mode")
                print("Using single-threaded mode")
                results = checker.check_all_accounts(callback=progress_callback)
            
            # Display summary
            summary = checker.get_results_summary()
            logger.info(f"Check completed: {summary['valid']} valid, {summary['error']} error, {summary['steamguard']} steamguard")
            print("\nCheck completed!")
            print(f"Total accounts: {summary['total']}")
            print(f"Valid accounts: {summary['valid']}")
            print(f"Error accounts: {summary['error']}")
            print(f"SteamGuard accounts: {summary['steamguard']}")
            
            # Export results if requested
            if export and summary['total'] > 0:
                logger.info(f"Exporting results to {export_format} format")
                print(f"\nExporting results to {export_format.upper()} format...")
                try:
                    result_files = exporter.export_by_status(results, export_format)
                    
                    for status, file_path in result_files.items():
                        logger.info(f"{status} accounts exported to: {file_path}")
                        print(f"{status} accounts exported to: {file_path}")
                    
                    if summary['valid'] > 0:
                        valid_file = exporter.combine_all_valid(results, export_format)
                        if valid_file:
                            logger.info(f"All valid accounts exported to: {valid_file}")
                            print(f"All valid accounts exported to: {valid_file}")
                except Exception as e:
                    logger.error(f"Error exporting results: {str(e)}", exc_info=True)
                    print(f"Error exporting results: {str(e)}")
                    
            return True
        except KeyboardInterrupt:
            logger.warning("Account checking interrupted by user")
            print("\nOperation cancelled by user. Stopping...")
            checker.stop_checking()
            print("Stopped. Some accounts may not have been checked.")
            return False
    except Exception as e:
        logger.error(f"Error in account checking process: {str(e)}", exc_info=True)
        print(f"Error in account checking process: {str(e)}")
        return False

def manage_proxies(args):
    """Manage proxy settings"""
    try:
        if args.add:
            # Validate proxy format
            is_valid, error_msg = validate_proxy(args.add)
            if not is_valid:
                logger.error(f"Invalid proxy format: {error_msg}")
                print(f"Error: {error_msg}")
                return False
                
            logger.info(f"Adding proxy: {args.add}")
            settings.proxies.append(args.add)
            settings.save_settings()
            print(f"Added proxy: {args.add}")
        
        if args.file:
            # Validate file path
            is_valid, error_msg = validate_file_path(args.file, must_exist=True, allowed_extensions=['.txt'])
            if not is_valid:
                logger.error(f"Invalid proxy file path: {error_msg}")
                print(f"Error: {error_msg}")
                return False
                
            logger.info(f"Loading proxies from file: {args.file}")
            if settings.load_proxies_from_file(args.file):
                settings.save_settings()
                print(f"Loaded proxies from {args.file}")
            else:
                logger.error(f"Failed to load proxies from file: {args.file}")
                print("Failed to load proxies from file")
        
        if args.enable:
            logger.info("Enabling proxies")
            settings.enable_proxies = True
            settings.save_settings()
            print("Proxies enabled")
        
        if args.disable:
            logger.info("Disabling proxies")
            settings.enable_proxies = False
            settings.save_settings()
            print("Proxies disabled")
        
        if args.test:
            logger.info("Testing proxies")
            proxy_manager.load_proxies()
            if proxy_manager.proxies:
                print(f"Testing {len(proxy_manager.proxies)} proxies...")
                working = proxy_manager.test_all_proxies()
                logger.info(f"{working} proxies are working")
                print(f"{working} proxies are working")
            else:
                logger.warning("No proxies to test")
                print("No proxies to test")
        
        # Display current proxy settings
        print("\nCurrent Proxy Settings:")
        print(f"Proxy usage: {'Enabled' if settings.enable_proxies else 'Disabled'}")
        print(f"Available proxies: {len(settings.proxies)}")
        for i, proxy in enumerate(settings.proxies, 1):
            print(f"  {i}. {proxy}")
        
        return True
    except Exception as e:
        logger.error(f"Error managing proxies: {str(e)}", exc_info=True)
        print(f"Error managing proxies: {str(e)}")
        return False

def start_gui():
    """Start the GUI application"""
    try:
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        
        # Create the application
        app = QApplication(sys.argv)
        app.setApplicationName("AccountHarvester")
        
        # Create and show the main window
        logger.info("Starting GUI")
        main_window = MainWindow()
        main_window.show()
        
        # Run the application
        return app.exec() == 0
    except Exception as e:
        logger.critical(f"Failed to start GUI: {str(e)}", exc_info=True)
        print(f"Error starting GUI: {str(e)}")
        return False

def main():
    """Main entry point for the application"""
    try:
        logger.info("Starting AccountHarvester")
        
        parser = setup_argparse()
        args = parser.parse_args()
        
        # Handle API key setting - securely store it
        if args.api_key:
            # Validate API key format
            is_valid, error_msg = validate_api_key(args.api_key)
            if not is_valid:
                logger.error(f"Invalid API key: {error_msg}")
                print(f"Error: {error_msg}")
                return False
                
            logger.info("Setting API key (value hidden)")
            settings.api_key = args.api_key
            settings.save_settings()
            # Only show first 5 characters followed by asterisks for security
            masked_key = args.api_key[:5] + "*" * (len(args.api_key) - 5) if len(args.api_key) > 5 else "*****"
            print(f"API key set: {masked_key}")
        
        # Handle rate limiting settings
        rate_limiting_updated = False
        
        if hasattr(args, 'rate_limit_enabled') and args.rate_limit_enabled is not None:
            settings.rate_limiting["enabled"] = args.rate_limit_enabled
            rate_limiting_updated = True
            logger.info(f"Rate limiting {'enabled' if args.rate_limit_enabled else 'disabled'}")
            print(f"Rate limiting {'enabled' if args.rate_limit_enabled else 'disabled'}")
            
        if hasattr(args, 'adaptive_rate_limiting') and args.adaptive_rate_limiting is not None:
            settings.rate_limiting["adaptive"] = args.adaptive_rate_limiting
            rate_limiting_updated = True
            logger.info(f"Adaptive rate limiting {'enabled' if args.adaptive_rate_limiting else 'disabled'}")
            print(f"Adaptive rate limiting {'enabled' if args.adaptive_rate_limiting else 'disabled'}")
            
        if hasattr(args, 'default_rate') and args.default_rate is not None:
            if args.default_rate <= 0:
                logger.warning(f"Invalid default rate {args.default_rate}, must be positive")
                print(f"Warning: Invalid default rate {args.default_rate}, must be positive")
            else:
                settings.rate_limiting["default_rate"] = args.default_rate
                rate_limiting_updated = True
                logger.info(f"Default rate limit set to {args.default_rate} requests/sec")
                print(f"Default rate limit set to {args.default_rate} requests/sec")
                
        if hasattr(args, 'player_service_rate') and args.player_service_rate is not None:
            if args.player_service_rate <= 0:
                logger.warning(f"Invalid player service rate {args.player_service_rate}, must be positive")
                print(f"Warning: Invalid player service rate {args.player_service_rate}, must be positive")
            else:
                settings.rate_limiting["player_service_rate"] = args.player_service_rate
                rate_limiting_updated = True
                logger.info(f"Player service rate limit set to {args.player_service_rate} requests/sec")
                print(f"Player service rate limit set to {args.player_service_rate} requests/sec")
                
        if hasattr(args, 'user_service_rate') and args.user_service_rate is not None:
            if args.user_service_rate <= 0:
                logger.warning(f"Invalid user service rate {args.user_service_rate}, must be positive")
                print(f"Warning: Invalid user service rate {args.user_service_rate}, must be positive")
            else:
                settings.rate_limiting["user_service_rate"] = args.user_service_rate
                rate_limiting_updated = True
                logger.info(f"User service rate limit set to {args.user_service_rate} requests/sec")
                print(f"User service rate limit set to {args.user_service_rate} requests/sec")
                
        if hasattr(args, 'store_api_rate') and args.store_api_rate is not None:
            if args.store_api_rate <= 0:
                logger.warning(f"Invalid store API rate {args.store_api_rate}, must be positive")
                print(f"Warning: Invalid store API rate {args.store_api_rate}, must be positive")
            else:
                settings.rate_limiting["store_api_rate"] = args.store_api_rate
                rate_limiting_updated = True
                logger.info(f"Store API rate limit set to {args.store_api_rate} requests/sec")
                print(f"Store API rate limit set to {args.store_api_rate} requests/sec")
                
        # Save settings and refresh rate limiters if any rate limiting settings were updated
        if rate_limiting_updated:
            settings.save_settings()
            # Import and update rate limiters
            from core.steam_api import steam_api
            steam_api.refresh_rate_limiters()
            logger.info("Rate limiters refreshed with new settings")
        
        # Handle auto-retry settings
        auto_retry_updated = False
        
        if hasattr(args, 'auto_retry_enabled') and args.auto_retry_enabled is not None:
            settings.auto_retry["enabled"] = args.auto_retry_enabled
            auto_retry_updated = True
            logger.info(f"Auto-retry {'enabled' if args.auto_retry_enabled else 'disabled'}")
            print(f"Auto-retry {'enabled' if args.auto_retry_enabled else 'disabled'}")
            
        if hasattr(args, 'max_retries') and args.max_retries is not None:
            if args.max_retries < 0:
                logger.warning(f"Invalid max retries {args.max_retries}, must be non-negative")
                print(f"Warning: Invalid max retries {args.max_retries}, must be non-negative")
            else:
                settings.auto_retry["max_retries"] = args.max_retries
                auto_retry_updated = True
                logger.info(f"Maximum retry attempts set to {args.max_retries}")
                print(f"Maximum retry attempts set to {args.max_retries}")
                
        if hasattr(args, 'initial_backoff') and args.initial_backoff is not None:
            if args.initial_backoff <= 0:
                logger.warning(f"Invalid initial backoff {args.initial_backoff}, must be positive")
                print(f"Warning: Invalid initial backoff {args.initial_backoff}, must be positive")
            else:
                settings.auto_retry["initial_backoff"] = args.initial_backoff
                auto_retry_updated = True
                logger.info(f"Initial backoff set to {args.initial_backoff} seconds")
                print(f"Initial backoff set to {args.initial_backoff} seconds")
                
        if hasattr(args, 'backoff_factor') and args.backoff_factor is not None:
            if args.backoff_factor <= 0:
                logger.warning(f"Invalid backoff factor {args.backoff_factor}, must be positive")
                print(f"Warning: Invalid backoff factor {args.backoff_factor}, must be positive")
            else:
                settings.auto_retry["backoff_factor"] = args.backoff_factor
                auto_retry_updated = True
                logger.info(f"Backoff factor set to {args.backoff_factor}")
                print(f"Backoff factor set to {args.backoff_factor}")
                
        if hasattr(args, 'jitter') and args.jitter is not None:
            if args.jitter < 0 or args.jitter > 1:
                logger.warning(f"Invalid jitter {args.jitter}, must be between 0 and 1")
                print(f"Warning: Invalid jitter {args.jitter}, must be between 0 and 1")
            else:
                settings.auto_retry["jitter"] = args.jitter
                auto_retry_updated = True
                logger.info(f"Jitter factor set to {args.jitter}")
                print(f"Jitter factor set to {args.jitter}")
                
        # Save settings if any auto-retry settings were updated
        if auto_retry_updated:
            settings.save_settings()
            logger.info("Auto-retry settings updated")
        
        # Initialize proxy manager
        try:
            logger.info("Initializing proxy manager")
            proxy_manager.load_proxies()
        except Exception as e:
            logger.error(f"Error loading proxies: {str(e)}", exc_info=True)
            print(f"Error loading proxies: {str(e)}")
        
        # Handle GUI mode
        if args.gui or len(sys.argv) <= 1:
            logger.info("Starting in GUI mode")
            return start_gui()
        
        # Handle commands
        if args.command == 'check':
            # Sanitize the credentials before logging
            sanitized_cred = args.credentials.split(':')[0] + ':******' if ':' in args.credentials else args.credentials
            logger.info(f"Checking single account: {sanitized_cred}")
            return check_single_account(args.credentials)
        elif args.command == 'file':
            return check_accounts_from_file(args.file_path, args.export, args.export_format, not args.no_threading)
        elif args.command == 'proxy':
            logger.info("Managing proxies")
            return manage_proxies(args)
        else:
            parser.print_help()
            return True
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        print("\nOperation cancelled by user")
        return False
    except Exception as e:
        logger.critical(f"Unhandled error in main: {str(e)}", exc_info=True)
        print(f"A critical error occurred: {str(e)}")
        print(f"Please check the log file: {logger.get_log_file_path()}")
        return False

if __name__ == "__main__":
    try:
        success = main()
        # Clean up resources
        try:
            # Clean up proxy connection pools
            logger.info("Cleaning up resources")
            proxy_manager.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
            
        if success:
            logger.info("Application completed successfully")
            sys.exit(0)
        else:
            logger.warning("Application completed with errors")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        print("\nOperation cancelled by user")
        # Clean up resources on keyboard interrupt
        try:
            proxy_manager.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup after interrupt: {str(e)}", exc_info=True)
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled application error: {str(e)}", exc_info=True)
        print(f"A critical application error occurred: {str(e)}")
        print(f"Please check the log file: {logger.get_log_file_path()}")
        # Attempt cleanup even after critical error
        try:
            proxy_manager.cleanup()
        except Exception as cleanup_error:
            logger.error(f"Error during cleanup after critical error: {str(cleanup_error)}", exc_info=True)
        sys.exit(1)
