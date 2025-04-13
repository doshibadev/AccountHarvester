"""
Settings tab for configuring application settings
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QGroupBox,
    QSpinBox, QCheckBox, QFileDialog, QStatusBar,
    QMessageBox, QDoubleSpinBox, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QComboBox, QTabWidget, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from config.settings import settings
from utils.input_validation import (
    validate_api_key, validate_file_path, validate_thread_count, 
    sanitize_input
)
from utils.logger import logger
from utils.cleanup import get_cache_stats, clear_cache, clear_old_logs, clear_temp_exports
from utils.config_backup import (
    create_backup, restore_backup, list_backups, 
    delete_backup, cleanup_old_backups
)
from core.proxy_manager import proxy_manager
import threading
from PyQt6.QtWidgets import QApplication

class SettingsTab(QWidget):
    """Tab for configuring application settings"""
    
    # Signal to notify when settings are updated
    settings_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        """Set up the user interface with nested tabs"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create nested tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs for different settings categories
        self.general_tab = self.create_general_tab()
        self.rate_limiting_tab = self.create_rate_limiting_tab()
        self.proxy_tab = self.create_proxy_tab()
        self.maintenance_tab = self.create_maintenance_tab()
        self.backup_tab = self.create_backup_tab()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.general_tab, "General")
        self.tab_widget.addTab(self.rate_limiting_tab, "Rate Limiting")
        self.tab_widget.addTab(self.proxy_tab, "Proxies")
        self.tab_widget.addTab(self.maintenance_tab, "Maintenance")
        self.tab_widget.addTab(self.backup_tab, "Backup/Restore")
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)
        
        # Save button
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        main_layout.addWidget(self.save_button)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        main_layout.addWidget(self.status_bar)
    
    def create_general_tab(self):
        """Create general settings tab with API and threading settings"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # API settings
        api_group = QGroupBox("Steam API Settings")
        api_layout = QFormLayout()
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your Steam API key")
        
        # Create a layout for the API key row with a button
        api_key_layout = QHBoxLayout()
        api_key_layout.addWidget(self.api_key_input)
        
        self.test_api_button = QPushButton("Test")
        self.test_api_button.clicked.connect(self.test_api_key)
        api_key_layout.addWidget(self.test_api_button)
        
        api_layout.addRow("API Key:", api_key_layout)
        
        api_info_label = QLabel(
            "Get your API key from: <a href='https://steamcommunity.com/dev/apikey'>https://steamcommunity.com/dev/apikey</a>"
        )
        api_info_label.setOpenExternalLinks(True)
        api_layout.addRow("", api_info_label)
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Threading settings
        threading_group = QGroupBox("Threading Settings")
        threading_layout = QFormLayout()
        
        self.thread_count_input = QSpinBox()
        self.thread_count_input.setRange(1, 10)
        self.thread_count_input.setValue(1)
        threading_layout.addRow("Thread Count:", self.thread_count_input)
        
        threading_group.setLayout(threading_layout)
        layout.addWidget(threading_group)
        
        # Add spacer to push everything to the top
        layout.addStretch()
        
        return tab
    
    def create_rate_limiting_tab(self):
        """Create tab for rate limiting and auto-retry settings"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Rate limiting settings
        rate_limit_group = QGroupBox("Rate Limiting Settings")
        rate_limit_layout = QVBoxLayout()
        
        # Enable/disable rate limiting
        self.enable_rate_limiting_checkbox = QCheckBox("Enable Rate Limiting")
        self.enable_rate_limiting_checkbox.setToolTip("Enable or disable rate limiting to prevent 429 errors")
        rate_limit_layout.addWidget(self.enable_rate_limiting_checkbox)
        
        # Adaptive rate limiting
        self.adaptive_rate_limiting_checkbox = QCheckBox("Adaptive Rate Limiting")
        self.adaptive_rate_limiting_checkbox.setToolTip(
            "Automatically adjust rate limits based on server responses"
        )
        rate_limit_layout.addWidget(self.adaptive_rate_limiting_checkbox)
        
        # Rate limit values
        rate_limit_form = QFormLayout()
        
        # Default rate
        self.default_rate_input = QDoubleSpinBox()
        self.default_rate_input.setRange(0.1, 10.0)
        self.default_rate_input.setSingleStep(0.1)
        self.default_rate_input.setDecimals(1)
        self.default_rate_input.setToolTip("Default requests per second")
        rate_limit_form.addRow("Default Rate:", self.default_rate_input)
        
        # Player service rate
        self.player_service_rate_input = QDoubleSpinBox()
        self.player_service_rate_input.setRange(0.1, 5.0)
        self.player_service_rate_input.setSingleStep(0.1)
        self.player_service_rate_input.setDecimals(1)
        self.player_service_rate_input.setToolTip("IPlayerService requests per second")
        rate_limit_form.addRow("Player Service Rate:", self.player_service_rate_input)
        
        # User service rate
        self.user_service_rate_input = QDoubleSpinBox()
        self.user_service_rate_input.setRange(0.1, 5.0)
        self.user_service_rate_input.setSingleStep(0.1)
        self.user_service_rate_input.setDecimals(1)
        self.user_service_rate_input.setToolTip("ISteamUser requests per second")
        rate_limit_form.addRow("User Service Rate:", self.user_service_rate_input)
        
        # Store API rate
        self.store_api_rate_input = QDoubleSpinBox()
        self.store_api_rate_input.setRange(0.1, 5.0)
        self.store_api_rate_input.setSingleStep(0.1)
        self.store_api_rate_input.setDecimals(1)
        self.store_api_rate_input.setToolTip("Steam Store API requests per second")
        rate_limit_form.addRow("Store API Rate:", self.store_api_rate_input)
        
        rate_limit_layout.addLayout(rate_limit_form)
        
        # Info label
        rate_limit_info = QLabel(
            "Lower values reduce the risk of rate limiting but increase processing time."
        )
        rate_limit_layout.addWidget(rate_limit_info)
        
        rate_limit_group.setLayout(rate_limit_layout)
        layout.addWidget(rate_limit_group)
        
        # Auto-retry settings
        retry_group = QGroupBox("Auto-Retry Settings")
        retry_layout = QVBoxLayout()
        
        # Enable/disable auto-retry
        self.enable_auto_retry_checkbox = QCheckBox("Enable Auto-Retry with Exponential Backoff")
        self.enable_auto_retry_checkbox.setToolTip("Automatically retry failed account checks with increasing delays")
        retry_layout.addWidget(self.enable_auto_retry_checkbox)
        
        # Auto-retry values
        retry_form = QFormLayout()
        
        # Max retries
        self.max_retries_input = QSpinBox()
        self.max_retries_input.setRange(0, 10)
        self.max_retries_input.setSingleStep(1)
        self.max_retries_input.setToolTip("Maximum number of retry attempts (0 = disabled)")
        retry_form.addRow("Max Retries:", self.max_retries_input)
        
        # Initial backoff
        self.initial_backoff_input = QDoubleSpinBox()
        self.initial_backoff_input.setRange(0.1, 30.0)
        self.initial_backoff_input.setSingleStep(0.5)
        self.initial_backoff_input.setDecimals(1)
        self.initial_backoff_input.setToolTip("Initial backoff time in seconds before the first retry")
        retry_form.addRow("Initial Backoff (s):", self.initial_backoff_input)
        
        # Backoff factor
        self.backoff_factor_input = QDoubleSpinBox()
        self.backoff_factor_input.setRange(1.0, 5.0)
        self.backoff_factor_input.setSingleStep(0.5)
        self.backoff_factor_input.setDecimals(1)
        self.backoff_factor_input.setToolTip("Multiplier for backoff time on each subsequent retry")
        retry_form.addRow("Backoff Factor:", self.backoff_factor_input)
        
        # Jitter
        self.jitter_input = QDoubleSpinBox()
        self.jitter_input.setRange(0.0, 1.0)
        self.jitter_input.setSingleStep(0.1)
        self.jitter_input.setDecimals(1)
        self.jitter_input.setToolTip("Random jitter factor to add to backoff (0.0-1.0)")
        retry_form.addRow("Jitter:", self.jitter_input)
        
        retry_layout.addLayout(retry_form)
        
        # Info label
        retry_info = QLabel(
            "Auto-retry helps recover from temporary network issues or rate limiting."
        )
        retry_layout.addWidget(retry_info)
        
        retry_group.setLayout(retry_layout)
        layout.addWidget(retry_group)
        
        # Add spacer
        layout.addStretch()
        
        return tab
    
    def create_proxy_tab(self):
        """Create tab for proxy settings"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Proxy settings
        proxy_group = QGroupBox("Proxy Settings")
        proxy_layout = QVBoxLayout()
        
        # Enable/disable proxies
        self.enable_proxies_checkbox = QCheckBox("Enable Proxies")
        proxy_layout.addWidget(self.enable_proxies_checkbox)
        
        # Proxy rotation settings
        proxy_rotation_form = QFormLayout()
        
        # Proxy rate limit cooldown
        self.proxy_cooldown_input = QSpinBox()
        self.proxy_cooldown_input.setRange(10, 300)
        self.proxy_cooldown_input.setSingleStep(10)
        self.proxy_cooldown_input.setValue(60)
        self.proxy_cooldown_input.setToolTip("Seconds to wait before using a rate-limited proxy again")
        proxy_rotation_form.addRow("Rate Limit Cooldown (s):", self.proxy_cooldown_input)
        
        # Auto rotate on rate limit
        self.auto_rotate_checkbox = QCheckBox("Auto-rotate Proxies on Rate Limit")
        self.auto_rotate_checkbox.setToolTip("Automatically switch to a different proxy when rate limits are detected")
        proxy_rotation_form.addRow("", self.auto_rotate_checkbox)
        
        proxy_layout.addLayout(proxy_rotation_form)
        
        # Proxy file selection
        proxy_file_layout = QHBoxLayout()
        
        self.proxy_file_label = QLabel("No proxy file selected")
        proxy_file_layout.addWidget(self.proxy_file_label, 1)
        
        self.browse_proxy_button = QPushButton("Browse")
        self.browse_proxy_button.clicked.connect(self.browse_proxy_file)
        proxy_file_layout.addWidget(self.browse_proxy_button)
        
        # Test proxies button
        self.test_proxies_button = QPushButton("Test Proxies")
        self.test_proxies_button.clicked.connect(self.test_proxies)
        proxy_file_layout.addWidget(self.test_proxies_button)
        
        proxy_layout.addLayout(proxy_file_layout)
        
        # Proxy status
        self.proxy_status_label = QLabel("No proxies loaded")
        proxy_layout.addWidget(self.proxy_status_label)
        
        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)
        
        # Add spacer
        layout.addStretch()
        
        return tab
    
    def create_maintenance_tab(self):
        """Create tab for cache and log maintenance"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Cache management
        cache_group = QGroupBox("Cache Management")
        cache_layout = QVBoxLayout()
        
        # Cache info
        cache_info_layout = QFormLayout()
        self.cache_files_label = QLabel("0 files")
        cache_info_layout.addRow("Cache Files:", self.cache_files_label)
        
        self.cache_size_label = QLabel("0 MB")
        cache_info_layout.addRow("Cache Size:", self.cache_size_label)
        
        self.oldest_cache_label = QLabel("N/A")
        cache_info_layout.addRow("Oldest Cache File:", self.oldest_cache_label)
        
        cache_layout.addLayout(cache_info_layout)
        
        # Cache buttons
        cache_buttons_layout = QHBoxLayout()
        
        # Clear cache button
        self.clear_cache_button = QPushButton("Clear Cache")
        self.clear_cache_button.setToolTip("Delete all cache files")
        self.clear_cache_button.clicked.connect(self.clear_cache)
        cache_buttons_layout.addWidget(self.clear_cache_button)
        
        # Clear old logs button
        self.clear_logs_button = QPushButton("Clear Old Logs")
        self.clear_logs_button.setToolTip("Delete log files older than 7 days")
        self.clear_logs_button.clicked.connect(self.clear_old_logs)
        cache_buttons_layout.addWidget(self.clear_logs_button)
        
        # Clear temporary exports button
        self.clear_exports_button = QPushButton("Clear Temp Exports")
        self.clear_exports_button.setToolTip("Delete temporary export files")
        self.clear_exports_button.clicked.connect(self.clear_temp_exports)
        cache_buttons_layout.addWidget(self.clear_exports_button)
        
        cache_layout.addLayout(cache_buttons_layout)
        
        # Cleanup settings
        cleanup_settings_form = QFormLayout()
        
        # Cache cleanup interval
        self.cache_cleanup_days_input = QSpinBox()
        self.cache_cleanup_days_input.setRange(1, 365)
        self.cache_cleanup_days_input.setValue(30)
        self.cache_cleanup_days_input.setToolTip("Age in days for cache files to delete during cleanup")
        cleanup_settings_form.addRow("Cache Cleanup Age (days):", self.cache_cleanup_days_input)
        
        # Logs cleanup days
        self.logs_cleanup_days_input = QSpinBox()
        self.logs_cleanup_days_input.setRange(1, 90)
        self.logs_cleanup_days_input.setValue(7)
        self.logs_cleanup_days_input.setToolTip("Age in days for log files to delete during cleanup")
        cleanup_settings_form.addRow("Logs Cleanup Age (days):", self.logs_cleanup_days_input)
        
        # Add cleanup settings form to layout
        cache_layout.addLayout(cleanup_settings_form)
        
        cache_group.setLayout(cache_layout)
        layout.addWidget(cache_group)
        
        # Add spacer
        layout.addStretch()
        
        return tab
    
    def create_backup_tab(self):
        """Create tab for configuration backup and restore"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Configuration backup/restore
        backup_group = QGroupBox("Configuration Backup/Restore")
        backup_layout = QVBoxLayout()
        
        # Backup list
        backup_list_layout = QVBoxLayout()
        
        self.backup_list = QListWidget()
        self.backup_list.setMinimumHeight(200)
        self.backup_list.setAlternatingRowColors(True)
        self.backup_list.itemDoubleClicked.connect(self.on_backup_item_double_clicked)
        backup_list_layout.addWidget(self.backup_list)
        
        # Backup buttons
        backup_buttons_layout = QHBoxLayout()
        
        # Create backup button
        self.create_backup_button = QPushButton("Create Backup")
        self.create_backup_button.setToolTip("Create a backup of current configuration")
        self.create_backup_button.clicked.connect(self.create_config_backup)
        backup_buttons_layout.addWidget(self.create_backup_button)
        
        # Restore backup button
        self.restore_backup_button = QPushButton("Restore Selected")
        self.restore_backup_button.setToolTip("Restore configuration from selected backup")
        self.restore_backup_button.clicked.connect(self.restore_config_backup)
        backup_buttons_layout.addWidget(self.restore_backup_button)
        
        # Delete backup button
        self.delete_backup_button = QPushButton("Delete Selected")
        self.delete_backup_button.setToolTip("Delete selected backup")
        self.delete_backup_button.clicked.connect(self.delete_config_backup)
        backup_buttons_layout.addWidget(self.delete_backup_button)
        
        # Refresh backup list button
        self.refresh_backups_button = QPushButton("Refresh")
        self.refresh_backups_button.setToolTip("Refresh backup list")
        self.refresh_backups_button.clicked.connect(self.refresh_backup_list)
        backup_buttons_layout.addWidget(self.refresh_backups_button)
        
        # Add buttons to layout
        backup_list_layout.addLayout(backup_buttons_layout)
        
        # Auto-cleanup settings
        backup_settings_form = QFormLayout()
        
        # Max backups to keep
        self.max_backups_input = QSpinBox()
        self.max_backups_input.setRange(1, 100)
        self.max_backups_input.setValue(10)
        self.max_backups_input.setToolTip("Maximum number of backups to keep")
        backup_settings_form.addRow("Max Backups to Keep:", self.max_backups_input)
        
        # Cleanup old backups button
        self.cleanup_backups_button = QPushButton("Cleanup Old Backups")
        self.cleanup_backups_button.setToolTip("Delete old backups, keeping only the most recent ones")
        self.cleanup_backups_button.clicked.connect(self.cleanup_old_config_backups)
        backup_settings_form.addRow("", self.cleanup_backups_button)
        
        # Add backup settings to layout
        backup_list_layout.addLayout(backup_settings_form)
        
        # Add list layout to main backup layout
        backup_layout.addLayout(backup_list_layout)
        
        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)
        
        # Add spacer
        layout.addStretch()
        
        return tab
    
    def load_settings(self):
        """Load settings from config"""
        # API settings
        if settings.api_key:
            # Show only first and last two characters of API key with asterisks in between for security
            api_key = settings.api_key
            if len(api_key) > 6:
                masked_key = api_key[:4] + "*" * (len(api_key) - 6) + api_key[-2:]
            else:
                masked_key = "******"  # Fallback for very short keys
            
            self.api_key_input.setText(masked_key)
            # Set placeholder to indicate this is a masked key
            self.api_key_input.setPlaceholderText("Enter to modify the API key")
            
        # Threading settings
        self.thread_count_input.setValue(settings.thread_count)
        
        # Rate limiting settings
        self.enable_rate_limiting_checkbox.setChecked(settings.rate_limiting.get("enabled", True))
        self.adaptive_rate_limiting_checkbox.setChecked(settings.rate_limiting.get("adaptive", True))
        self.default_rate_input.setValue(settings.rate_limiting.get("default_rate", 1.0))
        self.player_service_rate_input.setValue(settings.rate_limiting.get("player_service_rate", 0.5))
        self.user_service_rate_input.setValue(settings.rate_limiting.get("user_service_rate", 0.5))
        self.store_api_rate_input.setValue(settings.rate_limiting.get("store_api_rate", 0.25))
        
        # Auto-retry settings
        self.enable_auto_retry_checkbox.setChecked(settings.auto_retry.get("enabled", True))
        self.max_retries_input.setValue(settings.auto_retry.get("max_retries", 3))
        self.initial_backoff_input.setValue(settings.auto_retry.get("initial_backoff", 1.0))
        self.backoff_factor_input.setValue(settings.auto_retry.get("backoff_factor", 2.0))
        self.jitter_input.setValue(settings.auto_retry.get("jitter", 0.1))
        
        # Proxy settings
        self.enable_proxies_checkbox.setChecked(settings.enable_proxies)
        
        # Load proxy cooldown time
        if hasattr(proxy_manager, 'rate_limit_cooldown'):
            self.proxy_cooldown_input.setValue(proxy_manager.rate_limit_cooldown)
        
        # Auto rotate is always enabled in our implementation, but we set the checkbox
        # to make it visually consistent
        self.auto_rotate_checkbox.setChecked(True)
        
        if settings.proxy_file:
            self.proxy_file_label.setText(settings.proxy_file)
            self.update_proxy_status()
        
        # Load cache settings
        if settings.cache_settings:
            if 'cleanup_interval' in settings.cache_settings:
                cleanup_days = settings.cache_settings.get('cleanup_interval', 3600) // 86400
                self.cache_cleanup_days_input.setValue(max(1, cleanup_days))
            
            if settings.cache_ttl and 'player_summary' in settings.cache_ttl:
                logs_cleanup_days = settings.cache_ttl.get('player_summary', 3600) // 86400 // 7
                self.logs_cleanup_days_input.setValue(max(1, logs_cleanup_days))
        
        # Update cache statistics
        self.update_cache_stats()
        
        # Update backup list
        self.refresh_backup_list()
    
    def update_cache_stats(self):
        """Update cache statistics display"""
        try:
            stats = get_cache_stats()
            
            if stats["file_count"] > 0:
                self.cache_files_label.setText(f"{stats['file_count']} files")
                size_mb = stats["total_size"] / (1024 * 1024)
                self.cache_size_label.setText(f"{size_mb:.2f} MB")
                
                # Display oldest file timestamp
                if stats["oldest_timestamp"]:
                    # Format timestamp to just show the date
                    date_str = stats["oldest_timestamp"].split("T")[0]
                    self.oldest_cache_label.setText(date_str)
                else:
                    self.oldest_cache_label.setText("N/A")
            else:
                self.cache_files_label.setText("0 files")
                self.cache_size_label.setText("0 MB")
                self.oldest_cache_label.setText("N/A")
        except Exception as e:
            logger.error(f"Error updating cache stats: {str(e)}")
            self.cache_files_label.setText("Error")
            self.cache_size_label.setText("Error")
            self.oldest_cache_label.setText("Error")
    
    def clear_cache(self):
        """Clear the cache files"""
        try:
            # Ask for confirmation
            reply = QMessageBox.question(
                self, 
                "Confirm Cache Cleanup",
                "Are you sure you want to clear all cache files?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Run in a separate thread to avoid blocking the UI
                def clear_cache_thread():
                    try:
                        deleted_count, freed_bytes = clear_cache()
                        size_mb = freed_bytes / (1024 * 1024)
                        self.status_bar.showMessage(f"Cleared {deleted_count} cache files ({size_mb:.2f} MB)")
                        
                        # Update cache statistics
                        self.update_cache_stats()
                    except Exception as e:
                        logger.error(f"Error clearing cache: {str(e)}")
                        self.status_bar.showMessage(f"Error clearing cache: {str(e)}")
                
                threading.Thread(target=clear_cache_thread, daemon=True).start()
                self.status_bar.showMessage("Clearing cache...")
        except Exception as e:
            logger.error(f"Error in clear_cache: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
    
    def clear_old_logs(self):
        """Clear old log files"""
        try:
            # Get age from input
            age_days = self.logs_cleanup_days_input.value()
            
            # Ask for confirmation
            reply = QMessageBox.question(
                self, 
                "Confirm Log Cleanup",
                f"Are you sure you want to clear logs older than {age_days} days?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Run in a separate thread to avoid blocking the UI
                def clear_logs_thread():
                    try:
                        deleted_count = clear_old_logs(age_days=age_days)
                        self.status_bar.showMessage(f"Cleared {deleted_count} log files")
                    except Exception as e:
                        logger.error(f"Error clearing logs: {str(e)}")
                        self.status_bar.showMessage(f"Error clearing logs: {str(e)}")
                
                threading.Thread(target=clear_logs_thread, daemon=True).start()
                self.status_bar.showMessage("Clearing old logs...")
        except Exception as e:
            logger.error(f"Error in clear_old_logs: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
    
    def clear_temp_exports(self):
        """Clear temporary export files"""
        try:
            # Get age from input
            age_days = 30  # Default to 30 days
            
            # Ask for confirmation
            reply = QMessageBox.question(
                self, 
                "Confirm Export Cleanup",
                f"Are you sure you want to clear temporary export files older than {age_days} days?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Run in a separate thread to avoid blocking the UI
                def clear_exports_thread():
                    try:
                        deleted_count = clear_temp_exports(age_days=age_days)
                        self.status_bar.showMessage(f"Cleared {deleted_count} temporary export files")
                    except Exception as e:
                        logger.error(f"Error clearing exports: {str(e)}")
                        self.status_bar.showMessage(f"Error clearing exports: {str(e)}")
                
                threading.Thread(target=clear_exports_thread, daemon=True).start()
                self.status_bar.showMessage("Clearing temporary export files...")
        except Exception as e:
            logger.error(f"Error in clear_temp_exports: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
    
    def save_settings(self):
        """Save settings to config"""
        # API settings
        api_key = self.api_key_input.text().strip()
        
        # Check if the API key is a masked key (contains asterisks)
        if api_key and "*" not in api_key:
            # Only update if the key doesn't contain asterisks (means it's a new key)
            # Validate API key format
            is_valid, error_msg = validate_api_key(api_key)
            if not is_valid:
                logger.error(f"Invalid API key: {error_msg}")
                QMessageBox.warning(self, "Invalid API Key", f"Error: {error_msg}")
                self.status_bar.showMessage(f"Invalid API key: {error_msg}")
                return False
                
            settings.api_key = api_key
            self.status_bar.showMessage("API key updated and encrypted")
        elif api_key and "*" in api_key and not settings.api_key:
            # If masked key but no existing key, warn the user
            self.status_bar.showMessage("Please enter a valid API key, not the masked placeholder")
            return False
        
        # Threading settings - validate thread count
        thread_count = self.thread_count_input.value()
        is_valid, error_msg, validated_count = validate_thread_count(thread_count)
        if not is_valid:
            logger.warning(f"Invalid thread count: {error_msg}")
            self.status_bar.showMessage(f"Thread count adjusted to {validated_count}")
            self.thread_count_input.setValue(validated_count)
            
        settings.thread_count = validated_count
        
        # Rate limiting settings
        rate_limiting = {
            "enabled": self.enable_rate_limiting_checkbox.isChecked(),
            "adaptive": self.adaptive_rate_limiting_checkbox.isChecked(),
            "default_rate": self.default_rate_input.value(),
            "player_service_rate": self.player_service_rate_input.value(),
            "user_service_rate": self.user_service_rate_input.value(),
            "store_api_rate": self.store_api_rate_input.value()
        }
        
        settings.rate_limiting = rate_limiting
        
        # Auto-retry settings
        auto_retry = {
            "enabled": self.enable_auto_retry_checkbox.isChecked(),
            "max_retries": self.max_retries_input.value(),
            "initial_backoff": self.initial_backoff_input.value(),
            "backoff_factor": self.backoff_factor_input.value(),
            "jitter": self.jitter_input.value(),
            "retry_network_errors": True  # Keep default for now
        }
        
        settings.update_auto_retry_settings(auto_retry)
        
        # Proxy settings
        settings.enable_proxies = self.enable_proxies_checkbox.isChecked()
        
        # Update proxy cooldown setting
        if hasattr(proxy_manager, 'rate_limit_cooldown'):
            proxy_manager.rate_limit_cooldown = self.proxy_cooldown_input.value()
        
        proxy_file = self.proxy_file_label.text()
        if proxy_file != "No proxy file selected":
            # Validate proxy file path
            is_valid, error_msg = validate_file_path(
                proxy_file, must_exist=True, allowed_extensions=['.txt']
            )
            if not is_valid:
                logger.error(f"Invalid proxy file: {error_msg}")
                QMessageBox.warning(self, "Invalid Proxy File", f"Error: {error_msg}")
                self.status_bar.showMessage(f"Invalid proxy file: {error_msg}")
                return False
                
            settings.proxy_file = proxy_file
            settings.load_proxies_from_file(proxy_file)
            
            # Update proxy status after loading
            self.update_proxy_status()
        
        # Update cache settings
        cache_settings = {
            "enabled": True,
            "use_compression": True,
            "max_memory_entries": 1000,
            "cleanup_interval": self.cache_cleanup_days_input.value() * 86400  # Convert days to seconds
        }
        
        settings.update_cache_settings(cache_settings)
        
        # Save settings to file
        if settings.save_settings():
            self.status_bar.showMessage("Settings saved successfully")
            
            # Refresh rate limiters in the Steam API
            from core.steam_api import steam_api
            steam_api.refresh_rate_limiters()
            
            # Emit signal that settings have been updated
            self.settings_updated.emit()
        else:
            self.status_bar.showMessage("Error saving settings")
    
    def update_proxy_status(self):
        """Update the proxy status label with current proxy stats"""
        if not proxy_manager.enabled:
            self.proxy_status_label.setText("Proxies are disabled")
            return
            
        try:
            status = proxy_manager.get_proxy_status()
            status_text = (f"Proxies: {status['total']} total, {status['available']} available, "
                         f"{status['failed']} failed, {status['rate_limited']} rate-limited")
            self.proxy_status_label.setText(status_text)
        except Exception as e:
            logger.error(f"Error getting proxy status: {e}")
            self.proxy_status_label.setText("Error getting proxy status")
    
    def test_proxies(self):
        """Test the loaded proxies and show results"""
        if not proxy_manager.enabled:
            self.status_bar.showMessage("Proxies are disabled")
            return
            
        if not proxy_manager.proxies:
            self.status_bar.showMessage("No proxies to test")
            return
            
        self.status_bar.showMessage(f"Testing {len(proxy_manager.proxies)} proxies...")
        QApplication.processEvents()  # Update UI immediately
            
        # Run the test in a separate thread to avoid blocking the UI
        def test_proxies_thread():
            try:
                working_count = proxy_manager.test_all_proxies()
                # Update UI from main thread
                self.status_bar.showMessage(f"Tested {len(proxy_manager.proxies)} proxies. {working_count} are working.")
                self.update_proxy_status()
            except Exception as e:
                logger.error(f"Error testing proxies: {e}")
                self.status_bar.showMessage(f"Error testing proxies: {e}")
        
        threading.Thread(target=test_proxies_thread, daemon=True).start()
    
    def browse_proxy_file(self):
        """Open file dialog to select proxy file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Proxy File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            # Validate file path before accepting it
            is_valid, error_msg = validate_file_path(
                file_path, must_exist=True, allowed_extensions=['.txt']
            )
            if not is_valid:
                logger.error(f"Invalid proxy file selected: {error_msg}")
                QMessageBox.warning(self, "Invalid File", f"Error: {error_msg}")
                return
                
            self.proxy_file_label.setText(file_path)
            self.status_bar.showMessage(f"Proxy file selected: {file_path}")
    
    def test_api_key(self):
        """Test the API key by making a request"""
        api_key = self.api_key_input.text().strip()
        
        if not api_key:
            self.status_bar.showMessage("Please enter an API key first")
            return
        
        # Check if the key is masked - don't test masked keys
        if "*" in api_key:
            self.status_bar.showMessage("Can't test masked API key. Enter a new key to test.")
            return
            
        # Validate API key format before testing
        is_valid, error_msg = validate_api_key(api_key)
        if not is_valid:
            logger.error(f"Invalid API key format: {error_msg}")
            QMessageBox.warning(self, "Invalid API Key", f"Error: {error_msg}")
            self.status_bar.showMessage(f"Invalid API key: {error_msg}")
            return
        
        # Temporarily set API key
        original_key = settings.api_key
        settings.api_key = api_key
        
        # Test API key
        from core.steam_api import steam_api
        success = steam_api.test_api_key()
        
        # Restore original key
        settings.api_key = original_key
        
        if success:
            self.status_bar.showMessage("API key is valid")
        else:
            self.status_bar.showMessage("API key is invalid or Steam API is unavailable")
    
    def refresh_backup_list(self):
        """Update the list of available backups"""
        try:
            self.backup_list.clear()
            backups = list_backups()
            
            if not backups:
                self.backup_list.addItem("No backups available")
                self.restore_backup_button.setEnabled(False)
                self.delete_backup_button.setEnabled(False)
                return
                
            self.restore_backup_button.setEnabled(True)
            self.delete_backup_button.setEnabled(True)
            
            for backup in backups:
                item = QListWidgetItem(f"{backup['date']} - {backup['size_kb']:.1f} KB")
                item.setData(Qt.ItemDataRole.UserRole, backup['path'])
                item.setToolTip(f"Backup file: {backup['filename']}")
                self.backup_list.addItem(item)
                
        except Exception as e:
            logger.error(f"Error refreshing backup list: {str(e)}")
            self.backup_list.clear()
            self.backup_list.addItem(f"Error: {str(e)}")
            self.restore_backup_button.setEnabled(False)
            self.delete_backup_button.setEnabled(False)
            
    def create_config_backup(self):
        """Create a backup of the current configuration"""
        try:
            # Save current settings first
            if not settings.save_settings():
                reply = QMessageBox.question(
                    self, 
                    "Save Settings First",
                    "Could not save current settings. Do you want to proceed with backup anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    self.status_bar.showMessage("Backup canceled")
                    return
            
            # Run in a separate thread to avoid blocking the UI
            def backup_thread():
                try:
                    backup_info = create_backup()
                    if backup_info:
                        self.status_bar.showMessage(f"Backup created: {backup_info['date']}")
                        # Refresh the backup list
                        self.refresh_backup_list()
                    else:
                        self.status_bar.showMessage("Failed to create backup")
                except Exception as e:
                    logger.error(f"Error in backup thread: {str(e)}")
                    self.status_bar.showMessage(f"Error creating backup: {str(e)}")
            
            threading.Thread(target=backup_thread, daemon=True).start()
            self.status_bar.showMessage("Creating backup...")
        except Exception as e:
            logger.error(f"Error creating backup: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
            
    def restore_config_backup(self):
        """Restore configuration from the selected backup"""
        try:
            # Get selected backup
            selected_items = self.backup_list.selectedItems()
            if not selected_items:
                self.status_bar.showMessage("No backup selected")
                return
                
            backup_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if not backup_path:
                self.status_bar.showMessage("Invalid backup selection")
                return
                
            # Ask for confirmation
            reply = QMessageBox.question(
                self, 
                "Confirm Restore",
                "Are you sure you want to restore configuration from this backup?\n\n"
                "The current configuration will be overwritten and the application will need to restart.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.status_bar.showMessage("Restore canceled")
                return
                
            # Run in a separate thread to avoid blocking the UI
            def restore_thread():
                try:
                    success = restore_backup(backup_path)
                    if success:
                        self.status_bar.showMessage(f"Configuration restored from backup")
                        
                        # Show message about application restart
                        QMessageBox.information(
                            self,
                            "Restart Required",
                            "Configuration has been restored successfully.\n\n"
                            "Please restart the application for changes to take effect."
                        )
                    else:
                        self.status_bar.showMessage("Failed to restore configuration")
                except Exception as e:
                    logger.error(f"Error in restore thread: {str(e)}")
                    self.status_bar.showMessage(f"Error restoring configuration: {str(e)}")
            
            threading.Thread(target=restore_thread, daemon=True).start()
            self.status_bar.showMessage("Restoring configuration...")
        except Exception as e:
            logger.error(f"Error restoring configuration: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
            
    def delete_config_backup(self):
        """Delete the selected backup"""
        try:
            # Get selected backup
            selected_items = self.backup_list.selectedItems()
            if not selected_items:
                self.status_bar.showMessage("No backup selected")
                return
                
            backup_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if not backup_path:
                self.status_bar.showMessage("Invalid backup selection")
                return
                
            # Ask for confirmation
            reply = QMessageBox.question(
                self, 
                "Confirm Delete",
                "Are you sure you want to delete this backup?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.status_bar.showMessage("Delete canceled")
                return
                
            # Delete the backup
            success = delete_backup(backup_path)
            if success:
                self.status_bar.showMessage(f"Backup deleted")
                self.refresh_backup_list()
            else:
                self.status_bar.showMessage("Failed to delete backup")
        except Exception as e:
            logger.error(f"Error deleting backup: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
            
    def cleanup_old_config_backups(self):
        """Delete old backups, keeping only the most recent ones"""
        try:
            keep_count = self.max_backups_input.value()
            
            # Ask for confirmation
            reply = QMessageBox.question(
                self, 
                "Confirm Cleanup",
                f"Are you sure you want to delete all but the {keep_count} most recent backups?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                self.status_bar.showMessage("Cleanup canceled")
                return
                
            # Run in a separate thread to avoid blocking the UI
            def cleanup_thread():
                try:
                    deleted_count = cleanup_old_backups(keep_count)
                    if deleted_count > 0:
                        self.status_bar.showMessage(f"Deleted {deleted_count} old backups")
                    else:
                        self.status_bar.showMessage("No backups were deleted")
                    
                    # Refresh the backup list
                    self.refresh_backup_list()
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {str(e)}")
                    self.status_bar.showMessage(f"Error cleaning up backups: {str(e)}")
            
            threading.Thread(target=cleanup_thread, daemon=True).start()
            self.status_bar.showMessage("Cleaning up old backups...")
        except Exception as e:
            logger.error(f"Error cleaning up backups: {str(e)}")
            self.status_bar.showMessage(f"Error: {str(e)}")
            
    def on_backup_item_double_clicked(self, item):
        """Handle double-click on a backup item (restore)"""
        self.restore_config_backup()
