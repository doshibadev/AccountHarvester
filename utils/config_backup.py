"""
Configuration backup and restore utilities for AccountHarvester

This module provides utilities for backing up and restoring application configuration.
"""

import os
import json
import shutil
import zipfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from utils.logger import logger


def get_backup_dir() -> Path:
    """Get or create the backup directory"""
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    return backup_dir


def list_backups() -> List[Dict[str, Any]]:
    """
    List all available configuration backups
    
    Returns:
        List of dictionaries with backup info (path, date, size)
    """
    backup_dir = get_backup_dir()
    backup_files = list(backup_dir.glob("*.zip"))
    
    backups = []
    for backup_file in sorted(backup_files, key=os.path.getmtime, reverse=True):
        timestamp = os.path.getmtime(backup_file)
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = backup_file.stat().st_size / 1024
        
        backups.append({
            "path": str(backup_file),
            "filename": backup_file.name,
            "date": date_str,
            "timestamp": timestamp,
            "size_kb": size_kb
        })
    
    return backups


def create_backup() -> Optional[Dict[str, Any]]:
    """
    Create a backup of the current configuration
    
    Returns:
        Dictionary with backup information or None on failure
    """
    try:
        backup_dir = get_backup_dir()
        
        # Create a timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"config_backup_{timestamp}.zip"
        
        # Files to backup
        config_file = Path("config/app_settings.json")
        
        if not config_file.exists():
            logger.error(f"Config file {config_file} not found")
            return None
        
        # Create zip file
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add config file
            zipf.write(config_file, arcname=config_file.name)
            
            # Add backup metadata
            metadata = {
                "created": datetime.now().isoformat(),
                "config_size": config_file.stat().st_size,
                "version": "1.0"  # Version of backup format
            }
            
            # Write metadata to the zip file
            zipf.writestr("metadata.json", json.dumps(metadata, indent=2))
        
        # Get backup info
        timestamp = os.path.getmtime(backup_file)
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = backup_file.stat().st_size / 1024
        
        backup_info = {
            "path": str(backup_file),
            "filename": backup_file.name,
            "date": date_str,
            "timestamp": timestamp,
            "size_kb": size_kb
        }
        
        logger.info(f"Configuration backup created: {backup_file}")
        return backup_info
        
    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}", exc_info=True)
        return None


def restore_backup(backup_path: str) -> bool:
    """
    Restore configuration from a backup
    
    Args:
        backup_path: Path to the backup file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Backup file {backup_file} not found")
            return False
        
        # Extract to a temporary directory
        temp_dir = Path("backups/temp_restore")
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        temp_dir.mkdir(exist_ok=True, parents=True)
        
        # Extract backup
        with zipfile.ZipFile(backup_file, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Verify metadata
        metadata_file = temp_dir / "metadata.json"
        if not metadata_file.exists():
            logger.error("Invalid backup: metadata.json not found")
            shutil.rmtree(temp_dir)
            return False
        
        # Create backup of current config before restoration
        config_file = Path("config/app_settings.json")
        if config_file.exists():
            # Create a backup with timestamp suffix
            timestamp = int(time.time())
            backup_current = Path(f"config/app_settings.json.bak.{timestamp}")
            shutil.copy2(config_file, backup_current)
            logger.info(f"Created backup of current config: {backup_current}")
        
        # Restore config file
        extracted_config = temp_dir / "app_settings.json"
        if not extracted_config.exists():
            logger.error("Invalid backup: app_settings.json not found")
            shutil.rmtree(temp_dir)
            return False
        
        # Ensure config directory exists
        config_dir = Path("config")
        config_dir.mkdir(exist_ok=True)
        
        # Copy the extracted config to the config directory
        shutil.copy2(extracted_config, config_file)
        
        # Clean up temp directory
        shutil.rmtree(temp_dir)
        
        logger.info(f"Configuration restored from backup: {backup_file}")
        return True
        
    except Exception as e:
        logger.error(f"Error restoring backup: {str(e)}", exc_info=True)
        # Try to clean up temp directory if it exists
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        except:
            pass
        return False


def delete_backup(backup_path: str) -> bool:
    """
    Delete a backup file
    
    Args:
        backup_path: Path to the backup file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Backup file {backup_path} not found")
            return False
        
        backup_file.unlink()
        logger.info(f"Deleted backup: {backup_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting backup: {str(e)}", exc_info=True)
        return False


def cleanup_old_backups(keep_count: int = 10) -> int:
    """
    Delete old backups, keeping only the specified number of recent backups
    
    Args:
        keep_count: Number of recent backups to keep
        
    Returns:
        Number of deleted backups
    """
    try:
        backups = list_backups()
        
        if len(backups) <= keep_count:
            return 0
        
        # Sort by timestamp (newest first)
        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Keep the first keep_count backups, delete the rest
        to_delete = backups[keep_count:]
        deleted_count = 0
        
        for backup in to_delete:
            if delete_backup(backup["path"]):
                deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old backups, kept {keep_count} recent ones")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old backups: {str(e)}", exc_info=True)
        return 0 