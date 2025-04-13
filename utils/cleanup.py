"""
Cleanup utilities for AccountHarvester

This module contains utilities for cleaning up temporary files and cache.
"""

import os
import shutil
import glob
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from utils.logger import logger


def get_cache_dir() -> Path:
    """Return the path to the cache directory."""
    return Path("cache")


def get_logs_dir() -> Path:
    """Return the path to the logs directory."""
    return Path("logs")


def get_exports_dir() -> Path:
    """Return the path to the exports directory."""
    return Path("exports")


def get_cache_stats() -> Dict[str, any]:
    """
    Get statistics about the cache directory.
    
    Returns:
        Dict with the following keys:
        - total_size: Total size of cache in bytes
        - file_count: Number of files in cache
        - oldest_file: Path to the oldest file
        - newest_file: Path to the newest file
        - oldest_timestamp: Timestamp of the oldest file
        - newest_timestamp: Timestamp of the newest file
    """
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        return {
            "total_size": 0,
            "file_count": 0,
            "oldest_file": None,
            "newest_file": None,
            "oldest_timestamp": None,
            "newest_timestamp": None
        }
    
    files = list(cache_dir.glob("*.*"))
    if not files:
        return {
            "total_size": 0,
            "file_count": 0,
            "oldest_file": None,
            "newest_file": None,
            "oldest_timestamp": None,
            "newest_timestamp": None
        }
    
    # Get file stats
    file_stats = [
        (f, f.stat().st_size, f.stat().st_mtime)
        for f in files
    ]
    
    # Sort by timestamp
    sorted_by_time = sorted(file_stats, key=lambda x: x[2])
    
    total_size = sum(stats[1] for stats in file_stats)
    oldest = sorted_by_time[0]
    newest = sorted_by_time[-1]
    
    return {
        "total_size": total_size,
        "file_count": len(files),
        "oldest_file": str(oldest[0]),
        "newest_file": str(newest[0]),
        "oldest_timestamp": datetime.fromtimestamp(oldest[2]).isoformat(),
        "newest_timestamp": datetime.fromtimestamp(newest[2]).isoformat()
    }


def clear_cache(age_days: Optional[int] = None, file_pattern: Optional[str] = None) -> Tuple[int, int]:
    """
    Clear cache files.
    
    Args:
        age_days: If provided, only delete files older than this many days
        file_pattern: If provided, only delete files matching this pattern
        
    Returns:
        Tuple of (deleted file count, total bytes freed)
    """
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        logger.warning(f"Cache directory {cache_dir} does not exist")
        return 0, 0
    
    pattern = "*.*" if file_pattern is None else file_pattern
    files = list(cache_dir.glob(pattern))
    
    if not files:
        logger.info(f"No cache files found matching pattern: {pattern}")
        return 0, 0
    
    deleted_count = 0
    freed_bytes = 0
    cutoff_time = None
    
    if age_days is not None:
        cutoff_time = time.time() - (age_days * 86400)  # 86400 = seconds in a day
    
    for file_path in files:
        delete_file = True
        
        if cutoff_time is not None:
            file_mtime = file_path.stat().st_mtime
            if file_mtime > cutoff_time:
                delete_file = False
        
        if delete_file:
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                deleted_count += 1
                freed_bytes += file_size
                logger.debug(f"Deleted cache file: {file_path}")
            except (PermissionError, OSError) as e:
                logger.error(f"Error deleting cache file {file_path}: {str(e)}")
    
    if deleted_count > 0:
        logger.info(f"Cleared {deleted_count} cache files ({freed_bytes / (1024*1024):.2f} MB)")
    
    return deleted_count, freed_bytes


def clear_old_logs(age_days: int = 7) -> int:
    """
    Delete log files older than the specified number of days.
    
    Args:
        age_days: Delete logs older than this many days
        
    Returns:
        Number of deleted log files
    """
    logs_dir = get_logs_dir()
    if not logs_dir.exists():
        logger.warning(f"Logs directory {logs_dir} does not exist")
        return 0
    
    cutoff_time = time.time() - (age_days * 86400)
    log_files = list(logs_dir.glob("*.log*"))  # Includes rotated logs
    
    deleted_count = 0
    
    for log_file in log_files:
        if log_file.is_file() and log_file.stat().st_mtime < cutoff_time:
            # Don't delete the current log file
            if logger.get_log_file_path() != str(log_file):
                try:
                    log_file.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old log file: {log_file}")
                except (PermissionError, OSError) as e:
                    logger.error(f"Error deleting log file {log_file}: {str(e)}")
    
    if deleted_count > 0:
        logger.info(f"Cleared {deleted_count} old log files")
    
    return deleted_count


def clear_temp_exports(age_days: int = 30) -> int:
    """
    Delete temporary export files older than the specified number of days.
    
    Args:
        age_days: Delete exports older than this many days
        
    Returns:
        Number of deleted export files
    """
    exports_dir = get_exports_dir()
    if not exports_dir.exists():
        logger.warning(f"Exports directory {exports_dir} does not exist")
        return 0
    
    cutoff_time = time.time() - (age_days * 86400)
    temp_export_files = list(exports_dir.glob("*_temp_*.??*"))  # Find temp files with any extension
    
    deleted_count = 0
    
    for export_file in temp_export_files:
        if export_file.is_file() and export_file.stat().st_mtime < cutoff_time:
            try:
                export_file.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old temporary export file: {export_file}")
            except (PermissionError, OSError) as e:
                logger.error(f"Error deleting export file {export_file}: {str(e)}")
    
    if deleted_count > 0:
        logger.info(f"Cleared {deleted_count} old temporary export files")
    
    return deleted_count


def cleanup_all(cache_age_days: Optional[int] = 30, logs_age_days: int = 7, exports_age_days: int = 30) -> Dict[str, int]:
    """
    Perform a full cleanup operation.
    
    Args:
        cache_age_days: Age in days for cache files to delete (None for all)
        logs_age_days: Age in days for log files to delete
        exports_age_days: Age in days for temporary export files to delete
        
    Returns:
        Dict with statistics on cleanup operation
    """
    logger.info("Starting full cleanup operation")
    
    cache_deleted, cache_bytes = clear_cache(age_days=cache_age_days)
    logs_deleted = clear_old_logs(age_days=logs_age_days)
    exports_deleted = clear_temp_exports(age_days=exports_age_days)
    
    logger.info("Cleanup operation completed")
    
    return {
        "cache_files_deleted": cache_deleted,
        "cache_bytes_freed": cache_bytes,
        "log_files_deleted": logs_deleted,
        "export_files_deleted": exports_deleted
    } 