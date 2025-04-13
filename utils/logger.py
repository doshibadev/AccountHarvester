import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

class Logger:
    """Custom logger for the application"""
    
    def __init__(self, name="AccountHarvester", max_bytes=5*1024*1024, backup_count=5):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # Create a unique log file name with timestamp
        self.log_file = self.log_dir / f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        
        # File handler for logging to file with rotation
        file_handler = RotatingFileHandler(
            self.log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Console handler for logging to console
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message):
        """Log info level message"""
        self.logger.info(message)
    
    def warning(self, message):
        """Log warning level message"""
        self.logger.warning(message)
    
    def error(self, message, exc_info=False):
        """Log error level message with optional stack trace"""
        self.logger.error(message, exc_info=exc_info)
    
    def debug(self, message):
        """Log debug level message"""
        self.logger.debug(message)
    
    def critical(self, message, exc_info=True):
        """Log critical level message with stack trace by default"""
        self.logger.critical(message, exc_info=exc_info)
    
    def exception(self, message):
        """Log exception with stack trace"""
        self.logger.exception(message)
        
    def get_log_file_path(self):
        """Get the path to the current log file"""
        return str(self.log_file) if hasattr(self, 'log_file') else None
    
    def get_all_log_files(self):
        """Get a list of all available log files"""
        if hasattr(self, 'log_dir') and self.log_dir.exists():
            return sorted(
                [str(f) for f in self.log_dir.glob('*.log*')],  # Include rotated logs with extensions
                key=os.path.getmtime,
                reverse=True
            )
        return []
    
    def log_stacktrace(self):
        """Log the current stack trace"""
        self.error("Stack trace:\n" + traceback.format_exc())

# Create a global logger instance
logger = Logger()

def setup_logging(level=logging.INFO, max_bytes=5*1024*1024, backup_count=5):
    """Configure application logging with the specified level and rotation settings
    
    Args:
        level: Logging level (default: logging.INFO)
        max_bytes: Maximum size in bytes before log rotation (default: 5MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    global logger
    logger = Logger(max_bytes=max_bytes, backup_count=backup_count)
    logger.logger.setLevel(level)
    return logger
