#!/usr/bin/env python3
"""
AccountHarvester - Steam account checker
Entry point script to launch the application
"""

import sys
import os
import traceback
import logging
import json
from pathlib import Path

# Ensure the package is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# Set up logging before importing other modules
from utils.logger import setup_logging, logger
from utils.cleanup import cleanup_all, get_cache_stats, clear_cache, clear_old_logs, clear_temp_exports
from utils.config_backup import create_backup, restore_backup, list_backups, delete_backup, cleanup_old_backups

def encrypt_api_keys():
    """Encrypt any unencrypted API keys in settings file"""
    try:
        from config.encrypt_keys import migrate_settings_file
        return migrate_settings_file()
    except Exception as e:
        logger.error(f"Error encrypting API keys: {str(e)}", exc_info=True)
        return False

def perform_cleanup(clean_all=False, clean_cache=False, clean_logs=False, clean_exports=False, cache_days=30, logs_days=7, exports_days=30):
    """
    Perform cleanup operations on temporary files and cache
    
    Args:
        clean_all: Whether to clean all temporary files
        clean_cache: Whether to clean cache files
        clean_logs: Whether to clean log files
        clean_exports: Whether to clean export files
        cache_days: Age in days for cache files to delete
        logs_days: Age in days for log files to delete
        exports_days: Age in days for export files to delete
        
    Returns:
        Dictionary with cleanup statistics
    """
    try:
        if clean_all:
            results = cleanup_all(
                cache_age_days=cache_days,
                logs_age_days=logs_days,
                exports_age_days=exports_days
            )
            return results
        
        results = {
            "cache_files_deleted": 0,
            "cache_bytes_freed": 0,
            "log_files_deleted": 0,
            "export_files_deleted": 0
        }
        
        if clean_cache:
            cache_deleted, cache_bytes = clear_cache(age_days=cache_days)
            results["cache_files_deleted"] = cache_deleted
            results["cache_bytes_freed"] = cache_bytes
            
        if clean_logs:
            logs_deleted = clear_old_logs(age_days=logs_days)
            results["log_files_deleted"] = logs_deleted
            
        if clean_exports:
            exports_deleted = clear_temp_exports(age_days=exports_days)
            results["export_files_deleted"] = exports_deleted
            
        return results
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        return {"error": str(e)}

def handle_backup_operations(args):
    """
    Handle backup operations based on command-line arguments
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Create a backup
        if args.create:
            print("Creating configuration backup...")
            backup_info = create_backup()
            
            if backup_info:
                print(f"Backup created: {backup_info['filename']}")
                print(f"Date: {backup_info['date']}")
                print(f"Size: {backup_info['size_kb']:.1f} KB")
                print(f"Path: {backup_info['path']}")
                return 0
            else:
                print("Failed to create backup")
                return 1
                
        # List backups
        if args.list:
            backups = list_backups()
            
            if not backups:
                print("No backups available")
                return 0
                
            print(f"Available backups ({len(backups)}):")
            for i, backup in enumerate(backups, 1):
                print(f"  {i}. {backup['date']} - {backup['size_kb']:.1f} KB - {backup['filename']}")
            return 0
            
        # Restore a backup
        if args.restore:
            # Check if it's a path or an index
            if args.restore.isdigit():
                # It's an index, convert to 1-based
                index = int(args.restore) - 1
                backups = list_backups()
                
                if not backups:
                    print("No backups available to restore")
                    return 1
                    
                if index < 0 or index >= len(backups):
                    print(f"Invalid backup index: {index + 1}")
                    print(f"Available indexes: 1-{len(backups)}")
                    return 1
                    
                backup_path = backups[index]['path']
            else:
                # It's a path
                backup_path = args.restore
                
            print(f"Restoring configuration from backup: {backup_path}")
            success = restore_backup(backup_path)
            
            if success:
                print("Configuration restored successfully")
                print("Please restart the application for changes to take effect")
                return 0
            else:
                print("Failed to restore configuration")
                return 1
                
        # Delete a backup
        if args.delete:
            # Check if it's a path or an index
            if args.delete.isdigit():
                # It's an index, convert to 1-based
                index = int(args.delete) - 1
                backups = list_backups()
                
                if not backups:
                    print("No backups available to delete")
                    return 1
                    
                if index < 0 or index >= len(backups):
                    print(f"Invalid backup index: {index + 1}")
                    print(f"Available indexes: 1-{len(backups)}")
                    return 1
                    
                backup_path = backups[index]['path']
            else:
                # It's a path
                backup_path = args.delete
                
            print(f"Deleting backup: {backup_path}")
            success = delete_backup(backup_path)
            
            if success:
                print("Backup deleted successfully")
                return 0
            else:
                print("Failed to delete backup")
                return 1
                
        # Cleanup old backups
        if args.cleanup_backups:
            keep_count = args.keep_count
            print(f"Cleaning up old backups, keeping {keep_count} most recent...")
            
            deleted_count = cleanup_old_backups(keep_count)
            
            if deleted_count > 0:
                print(f"Deleted {deleted_count} old backups")
            else:
                print("No backups were deleted")
                
            return 0
                
        # If no specific operation is requested, show help
        print("No backup operation specified")
        print("Use --help to see available options")
        return 1
            
    except Exception as e:
        logger.error(f"Error during backup operation: {str(e)}", exc_info=True)
        print(f"Error: {str(e)}")
        return 1

def main():
    try:
        # Configure logging with rotation
        setup_logging(level=logging.INFO, max_bytes=10*1024*1024, backup_count=5)
        logger.info("Starting AccountHarvester application")
        
        # Check for command-line arguments
        if len(sys.argv) > 1:
            import argparse
            
            # Handle cleanup command
            if sys.argv[1] == "cleanup":
                # Parse cleanup-specific arguments
                parser = argparse.ArgumentParser(description='AccountHarvester Cleanup Utility')
                parser.add_argument('--all', action='store_true', help='Clean all temporary files and cache')
                parser.add_argument('--cache', action='store_true', help='Clean cache files')
                parser.add_argument('--logs', action='store_true', help='Clean old log files')
                parser.add_argument('--exports', action='store_true', help='Clean temporary export files')
                parser.add_argument('--cache-days', type=int, default=30, help='Age in days for cache files to delete')
                parser.add_argument('--logs-days', type=int, default=7, help='Age in days for log files to delete')
                parser.add_argument('--exports-days', type=int, default=30, help='Age in days for export files to delete')
                parser.add_argument('--stats', action='store_true', help='Show cache statistics')
                
                # Skip the "cleanup" argument
                cleanup_args = parser.parse_args(sys.argv[2:])
                
                # If no specific cleanup option is selected, show help and stats
                if not any([cleanup_args.all, cleanup_args.cache, cleanup_args.logs, cleanup_args.exports]):
                    if not cleanup_args.stats:
                        parser.print_help()
                        print("\nCache Statistics:")
                    else:
                        print("Cache Statistics:")
                    
                    # Show cache statistics
                    stats = get_cache_stats()
                    if stats["file_count"] > 0:
                        size_mb = stats["total_size"] / (1024 * 1024)
                        print(f"  Total files: {stats['file_count']}")
                        print(f"  Total size: {size_mb:.2f} MB")
                        print(f"  Oldest file: {stats['oldest_file']} ({stats['oldest_timestamp']})")
                        print(f"  Newest file: {stats['newest_file']} ({stats['newest_timestamp']})")
                    else:
                        print("  No cache files found.")
                    return 0
                
                # Perform cleanup based on arguments
                results = perform_cleanup(
                    clean_all=cleanup_args.all,
                    clean_cache=cleanup_args.cache or cleanup_args.all,
                    clean_logs=cleanup_args.logs or cleanup_args.all,
                    clean_exports=cleanup_args.exports or cleanup_args.all,
                    cache_days=cleanup_args.cache_days,
                    logs_days=cleanup_args.logs_days,
                    exports_days=cleanup_args.exports_days
                )
                
                if "error" in results:
                    print(f"Error during cleanup: {results['error']}")
                    return 1
                    
                # Print results
                print("Cleanup completed:")
                if results["cache_files_deleted"] > 0:
                    size_mb = results["cache_bytes_freed"] / (1024 * 1024)
                    print(f"  Deleted {results['cache_files_deleted']} cache files ({size_mb:.2f} MB)")
                
                if results["log_files_deleted"] > 0:
                    print(f"  Deleted {results['log_files_deleted']} old log files")
                    
                if results["export_files_deleted"] > 0:
                    print(f"  Deleted {results['export_files_deleted']} temporary export files")
                    
                if (results["cache_files_deleted"] + results["log_files_deleted"] + results["export_files_deleted"]) == 0:
                    print("  No files were deleted.")
                    
                return 0
            
            # Handle backup command
            elif sys.argv[1] == "backup":
                # Parse backup-specific arguments
                parser = argparse.ArgumentParser(description='AccountHarvester Backup Utility')
                parser.add_argument('--create', action='store_true', help='Create a new configuration backup')
                parser.add_argument('--list', action='store_true', help='List available backups')
                parser.add_argument('--restore', metavar='BACKUP', help='Restore configuration from backup (path or index)')
                parser.add_argument('--delete', metavar='BACKUP', help='Delete a backup (path or index)')
                parser.add_argument('--cleanup-backups', action='store_true', help='Clean up old backups')
                parser.add_argument('--keep-count', type=int, default=10, help='Number of recent backups to keep (default: 10)')
                
                # Skip the "backup" argument
                backup_args = parser.parse_args(sys.argv[2:])
                
                # If no specific operation is selected, show help
                if not any([backup_args.create, backup_args.list, backup_args.restore, backup_args.delete, backup_args.cleanup_backups]):
                    parser.print_help()
                    return 0
                
                # Handle backup operations
                return handle_backup_operations(backup_args)
                
        # Migrate any unencrypted API keys to encrypted format
        encrypt_api_keys()
        
        # Run the application
        from app import main as app_main
        return app_main()
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        return 1
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"A critical error occurred. Please check the logs at: {logger.get_log_file_path()}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 