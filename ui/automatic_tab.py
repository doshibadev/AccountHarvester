"""
Automatic tab for checking multiple accounts from a file
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFileDialog, QGroupBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QStatusBar,
    QSpinBox, QCheckBox, QMessageBox, QProgressDialog,
    QComboBox, QFrame, QLineEdit, QInputDialog, QTabWidget,
    QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QSortFilterProxyModel
from PyQt6.QtGui import QColor, QFont, QPalette
from core.account import AccountChecker, AccountStatus
from core.exporter import exporter
from config.settings import settings
from utils.logger import logger
from utils.input_validation import validate_file_path, validate_thread_count
import os
import time
import threading
import datetime

class FilterSortFrame(QFrame):
    """Frame containing filtering and sorting controls"""
    filterChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("background-color: #2a2a2a; border: 1px solid #555555; border-radius: 3px;")
        self.presets = {}
        self.setup_ui()
        self.load_presets()
        
    def setup_ui(self):
        """Set up the filter and sort controls"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Filter & Sort")
        title_label.setStyleSheet("font-weight: bold; color: #cccccc;")
        layout.addWidget(title_label)
        
        # Filter by status
        filter_status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setStyleSheet("color: #cccccc;")
        filter_status_layout.addWidget(status_label)
        
        self.status_filter = QComboBox()
        self.status_filter.addItem("All", None)
        self.status_filter.addItem("Valid", AccountStatus.VALID.value)
        self.status_filter.addItem("Error", AccountStatus.ERROR.value)
        self.status_filter.addItem("SteamGuard", AccountStatus.STEAMGUARD.value)
        self.status_filter.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555;")
        self.status_filter.currentIndexChanged.connect(self.on_filter_changed)
        filter_status_layout.addWidget(self.status_filter)
        
        # Games filter
        has_games_layout = QHBoxLayout()
        games_label = QLabel("Games:")
        games_label.setStyleSheet("color: #cccccc;")
        has_games_layout.addWidget(games_label)
        
        self.games_filter = QComboBox()
        self.games_filter.addItem("All", None)
        self.games_filter.addItem("Has Games", True)
        self.games_filter.addItem("No Games", False)
        self.games_filter.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555;")
        self.games_filter.currentIndexChanged.connect(self.on_filter_changed)
        has_games_layout.addWidget(self.games_filter)
        
        filter_status_layout.addLayout(has_games_layout)
        layout.addLayout(filter_status_layout)
        
        # Search filter
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("color: #cccccc;")
        search_layout.addWidget(search_label)
        
        self.search_filter = QLineEdit()
        self.search_filter.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555; padding: 3px;")
        self.search_filter.setPlaceholderText("Search by username or error message...")
        self.search_filter.textChanged.connect(self.on_filter_changed)
        search_layout.addWidget(self.search_filter)
        
        layout.addLayout(search_layout)
        
        # Sort options
        sort_layout = QHBoxLayout()
        sort_label = QLabel("Sort by:")
        sort_label.setStyleSheet("color: #cccccc;")
        sort_layout.addWidget(sort_label)
        
        self.sort_column = QComboBox()
        self.sort_column.addItem("Username", 0)
        self.sort_column.addItem("Status", 1)
        self.sort_column.addItem("Games Count", 2)
        self.sort_column.addItem("Error Message", 3)
        self.sort_column.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555;")
        self.sort_column.currentIndexChanged.connect(self.on_filter_changed)
        sort_layout.addWidget(self.sort_column)
        
        self.sort_order = QComboBox()
        self.sort_order.addItem("Ascending", Qt.SortOrder.AscendingOrder)
        self.sort_order.addItem("Descending", Qt.SortOrder.DescendingOrder)
        self.sort_order.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555;")
        self.sort_order.currentIndexChanged.connect(self.on_filter_changed)
        sort_layout.addWidget(self.sort_order)
        
        layout.addLayout(sort_layout)
        
        # Presets
        presets_layout = QHBoxLayout()
        presets_label = QLabel("Presets:")
        presets_label.setStyleSheet("color: #cccccc;")
        presets_layout.addWidget(presets_label)
        
        self.preset_combo = QComboBox()
        self.preset_combo.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555;")
        self.preset_combo.currentIndexChanged.connect(self.load_preset)
        presets_layout.addWidget(self.preset_combo, 1)
        
        save_preset_button = QPushButton("Save")
        save_preset_button.setStyleSheet("background-color: #2d2d2d; color: #ffffff; padding: 3px; border: 1px solid #555555;")
        save_preset_button.clicked.connect(self.save_preset)
        save_preset_button.setToolTip("Save current filter settings as a preset")
        presets_layout.addWidget(save_preset_button)
        
        layout.addLayout(presets_layout)
        
        # Apply/Reset buttons
        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("Reset Filters")
        self.reset_button.setStyleSheet("background-color: #2d2d2d; color: #ffffff; padding: 5px; border: 1px solid #555555;")
        self.reset_button.clicked.connect(self.reset_filters)
        button_layout.addWidget(self.reset_button)
        
        layout.addLayout(button_layout)
    
    def on_filter_changed(self):
        """Called when any filter or sort option is changed"""
        self.filterChanged.emit()
    
    def reset_filters(self):
        """Reset all filters to default values"""
        self.status_filter.setCurrentIndex(0)
        self.games_filter.setCurrentIndex(0)
        self.search_filter.clear()
        self.sort_column.setCurrentIndex(0)
        self.sort_order.setCurrentIndex(0)
        self.filterChanged.emit()
    
    def get_filters(self):
        """Get the current filter settings"""
        return {
            'status': self.status_filter.currentData(),
            'has_games': self.games_filter.currentData(),
            'search': self.search_filter.text(),
            'sort_column': self.sort_column.currentData(),
            'sort_order': self.sort_order.currentData()
        }
        
    def save_preset(self):
        """Save the current filter settings as a preset"""
        preset_name, ok = QInputDialog.getText(
            self, "Save Filter Preset", "Enter a name for this filter preset:"
        )
        
        if ok and preset_name:
            # Get current filter settings
            current_filters = self.get_filters()
            
            # Add or update the preset
            self.presets[preset_name] = current_filters
            
            # Update the presets combo box
            current_index = self.preset_combo.findText(preset_name)
            if current_index == -1:
                self.preset_combo.addItem(preset_name)
            
            # Save presets to settings
            self._save_presets_to_settings()
            
            logger.info(f"Saved filter preset: {preset_name}")
    
    def load_preset(self, index):
        """Load the selected preset"""
        if index <= 0:  # Skip the first item which is empty
            return
            
        preset_name = self.preset_combo.itemText(index)
        if preset_name in self.presets:
            filters = self.presets[preset_name]
            
            # Set status filter
            status_index = 0  # Default to "All"
            if filters['status'] == AccountStatus.VALID.value:
                status_index = 1
            elif filters['status'] == AccountStatus.ERROR.value:
                status_index = 2
            elif filters['status'] == AccountStatus.STEAMGUARD.value:
                status_index = 3
            self.status_filter.setCurrentIndex(status_index)
            
            # Set has games filter
            games_index = 0  # Default to "All"
            if filters['has_games'] is True:
                games_index = 1
            elif filters['has_games'] is False:
                games_index = 2
            self.games_filter.setCurrentIndex(games_index)
            
            # Set search text
            self.search_filter.setText(filters.get('search', ''))
            
            # Set sort column
            sort_col = filters.get('sort_column', 0)
            self.sort_column.setCurrentIndex(self.sort_column.findData(sort_col))
            
            # Set sort order
            sort_order = filters.get('sort_order', Qt.SortOrder.AscendingOrder)
            self.sort_order.setCurrentIndex(self.sort_order.findData(sort_order))
            
            logger.info(f"Loaded filter preset: {preset_name}")
    
    def load_presets(self):
        """Load saved presets from settings"""
        try:
            from config.settings import settings
            
            if hasattr(settings, 'filter_presets') and settings.filter_presets:
                self.presets = settings.filter_presets
                
                # Populate the presets combo box
                self.preset_combo.clear()
                self.preset_combo.addItem("-- Select Preset --")
                for preset_name in self.presets:
                    self.preset_combo.addItem(preset_name)
                    
                logger.info(f"Loaded {len(self.presets)} filter presets from settings")
        except Exception as e:
            logger.error(f"Error loading filter presets: {e}")
    
    def _save_presets_to_settings(self):
        """Save presets to application settings"""
        try:
            from config.settings import settings
            
            # Store the presets in settings
            settings.filter_presets = self.presets
            settings.save()
            
            logger.info(f"Saved {len(self.presets)} filter presets to settings")
        except Exception as e:
            logger.error(f"Error saving filter presets: {e}")

class AccountCheckWorker(QThread):
    """Worker thread for checking accounts"""
    progress_update = pyqtSignal(int, int, object)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, file_path, use_threading=True, thread_count=None):
        super().__init__()
        self.file_path = file_path
        self.checker = AccountChecker()
        self.should_stop = False
        self.use_threading = use_threading
        self.thread_count = thread_count
        
    def run(self):
        """Run the account checking process"""
        try:
            # Load accounts
            logger.info(f"Loading accounts from file: {self.file_path}")
            num_accounts = self.checker.add_accounts_from_file(self.file_path)
            
            if num_accounts == 0:
                logger.warning("No valid accounts found in the file")
                self.error.emit("No valid accounts found in the file")
                self.finished.emit({})
                return
            
            # Define progress callback
            def progress_callback(current, total, account):
                self.progress_update.emit(current, total, account)
            
            # Check if using threading or single-thread mode
            if self.use_threading:
                logger.info(f"Starting to check {num_accounts} accounts using threading")
                # Run the checker with threading
                results = self.checker.check_all_accounts_threaded(
                    callback=progress_callback,
                    max_workers=self.thread_count
                )
            else:
                logger.info(f"Starting to check {num_accounts} accounts (single-threaded)")
                # Run the checker without threading
                results = self.checker.check_all_accounts(callback=progress_callback)
            
            # Signal completion
            logger.info(f"Account checking completed with {len(results.get(AccountStatus.VALID, []))} valid accounts")
            self.finished.emit(results)
            
        except Exception as e:
            logger.error(f"Error in account check worker: {e}")
            self.error.emit(f"Error checking accounts: {e}")
            self.finished.emit({})
    
    def stop(self):
        """Stop the checking process"""
        if self.checker:
            logger.info("Stopping account checking process")
            self.checker.stop_checking()
            self.should_stop = True

class AutomaticTab(QWidget):
    """Tab for automatically checking multiple accounts from a file"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize member variables
        self.selected_file = None
        self.checking_worker = None
        self.start_time = None
        self.elapsed_timer = None
        self.stop_requested = False
        
        # Status counters
        self.total_accounts = 0
        self.valid_accounts = 0
        self.error_accounts = 0
        self.steamguard_accounts = 0
        self.accounts_with_games = 0
        
        # Results
        self.accounts = []
        self.filtered_accounts = []
        
        # UI setup
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface with nested tabs"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # File selection and control section (always visible)
        self.setup_file_selection(main_layout)
        
        # Create nested tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs for different sections
        self.results_tab = self.create_results_tab()
        self.filters_tab = self.create_filters_tab()
        self.export_tab = self.create_export_tab()
        self.stats_tab = self.create_stats_tab()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.results_tab, "Results")
        self.tab_widget.addTab(self.filters_tab, "Filters & Sorting")
        self.tab_widget.addTab(self.export_tab, "Export")
        self.tab_widget.addTab(self.stats_tab, "Statistics")
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)
        
        # Status bar (always visible)
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        main_layout.addWidget(self.status_bar)
    
    def setup_file_selection(self, parent_layout):
        """Set up the file selection and control section"""
        # Group box styling
        group_box_style = """
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """
        
        # File selection
        file_group = QGroupBox("Account List")
        file_group.setStyleSheet(group_box_style)
        file_layout = QVBoxLayout()
        
        select_layout = QHBoxLayout()
        
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet("color: #cccccc;")
        select_layout.addWidget(self.file_path_label, 1)
        
        self.browse_button = QPushButton("Browse")
        self.browse_button.setStyleSheet("background-color: #2d2d2d; color: #ffffff; padding: 5px; border: 1px solid #555555;")
        self.browse_button.clicked.connect(self.browse_file)
        select_layout.addWidget(self.browse_button)
        
        file_layout.addLayout(select_layout)
        
        # Threading options
        threading_layout = QHBoxLayout()
        
        self.use_threading_checkbox = QCheckBox("Use Multi-Threading")
        self.use_threading_checkbox.setChecked(True)
        self.use_threading_checkbox.setStyleSheet("color: #cccccc;")
        threading_layout.addWidget(self.use_threading_checkbox)
        
        thread_count_layout = QHBoxLayout()
        thread_count_label = QLabel("Thread Count:")
        thread_count_label.setStyleSheet("color: #cccccc;")
        thread_count_layout.addWidget(thread_count_label)
        
        self.thread_count_spinner = QSpinBox()
        self.thread_count_spinner.setRange(1, 20)
        self.thread_count_spinner.setValue(settings.thread_count)
        self.thread_count_spinner.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555;")
        thread_count_layout.addWidget(self.thread_count_spinner)
        
        threading_layout.addLayout(thread_count_layout)
        threading_layout.addStretch()
        
        file_layout.addLayout(threading_layout)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        button_style = "background-color: #2d2d2d; color: #ffffff; padding: 6px; border: 1px solid #555555;"
        
        self.check_button = QPushButton("Check Accounts")
        self.check_button.clicked.connect(self.check_accounts)
        self.check_button.setStyleSheet(button_style)
        self.check_button.setToolTip("Start checking accounts from the selected file")
        control_layout.addWidget(self.check_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_checking)
        self.stop_button.setDisabled(True)
        self.stop_button.setStyleSheet(button_style)
        self.stop_button.setToolTip("Stop the current checking process")
        control_layout.addWidget(self.stop_button)
        
        file_layout.addLayout(control_layout)
        
        # Progress section
        progress_layout = QHBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #2d2d2d; color: #cccccc; border: 1px solid #555555; text-align: center; } QProgressBar::chunk { background-color: #3a7ebf; }")
        progress_layout.addWidget(self.progress_bar, 1)
        
        # Elapsed time label
        self.elapsed_label = QLabel("Elapsed: 00:00:00")
        self.elapsed_label.setStyleSheet("color: #cccccc;")
        progress_layout.addWidget(self.elapsed_label)
        
        file_layout.addLayout(progress_layout)
        
        # Status counters
        self.create_status_counter_layout(file_layout)
        
        file_group.setLayout(file_layout)
        parent_layout.addWidget(file_group)
    
    def create_results_tab(self):
        """Create tab for results table"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Results table
        table_group = QGroupBox("Results")
        table_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        table_layout = QVBoxLayout()
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Username", "Status", "Games", "Error Message", "SteamID"])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a2a;
                color: #cccccc;
                gridline-color: #555555;
                border: 1px solid #555555;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #3a7ebf;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 5px;
                border: 1px solid #555555;
            }
        """)
        table_layout.addWidget(self.results_table)
        
        # Table control buttons
        table_buttons_layout = QHBoxLayout()
        
        button_style = "background-color: #2d2d2d; color: #ffffff; padding: 5px; border: 1px solid #555555;"
        
        self.clear_table_button = QPushButton("Clear Results")
        self.clear_table_button.setStyleSheet(button_style)
        self.clear_table_button.clicked.connect(self.reset_results_table)
        table_buttons_layout.addWidget(self.clear_table_button)
        
        table_buttons_layout.addStretch()
        
        table_layout.addLayout(table_buttons_layout)
        
        table_group.setLayout(table_layout)
        layout.addWidget(table_group)
        
        return tab
    
    def create_filters_tab(self):
        """Create tab for filters and sorting"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Filter and sort frame
        self.filter_frame = FilterSortFrame()
        self.filter_frame.filterChanged.connect(self.apply_filters)
        layout.addWidget(self.filter_frame)
        
        # Add spacer
        layout.addStretch()
        
        return tab
    
    def create_export_tab(self):
        """Create tab for export settings"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Export settings
        export_group = QGroupBox("Export Settings")
        export_layout = QVBoxLayout()
        
        # File format section
        format_layout = QFormLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["CSV", "TXT", "JSON", "XML", "YAML"])
        format_layout.addRow("Export Format:", self.format_combo)
        
        # Separator option (for CSV/TXT)
        self.separator_combo = QComboBox()
        self.separator_combo.addItems(["Comma (,)", "Semicolon (;)", "Tab", "Pipe (|)"])
        format_layout.addRow("Field Separator:", self.separator_combo)
        
        # Include header option
        self.include_header_checkbox = QCheckBox("Include Header Row")
        self.include_header_checkbox.setChecked(True)
        format_layout.addRow("", self.include_header_checkbox)
        
        export_layout.addLayout(format_layout)
        
        # Fields to include section
        include_fields_group = QGroupBox("Fields to Include")
        include_fields_group.setObjectName("Fields to Include")
        include_fields_layout = QVBoxLayout()
        
        # Account info fields
        self.include_username_checkbox = QCheckBox("Username")
        self.include_username_checkbox.setChecked(True)
        include_fields_layout.addWidget(self.include_username_checkbox)
        
        self.include_password_checkbox = QCheckBox("Password")
        self.include_password_checkbox.setChecked(True)
        include_fields_layout.addWidget(self.include_password_checkbox)
        
        self.include_status_checkbox = QCheckBox("Status")
        self.include_status_checkbox.setChecked(True)
        include_fields_layout.addWidget(self.include_status_checkbox)
        
        self.include_steamid_checkbox = QCheckBox("Steam ID")
        self.include_steamid_checkbox.setChecked(True)
        include_fields_layout.addWidget(self.include_steamid_checkbox)
        
        self.include_email_checkbox = QCheckBox("Email")
        self.include_email_checkbox.setChecked(True)
        include_fields_layout.addWidget(self.include_email_checkbox)
        
        # Game-related fields
        self.include_games_count_checkbox = QCheckBox("Games Count")
        self.include_games_count_checkbox.setChecked(True)
        include_fields_layout.addWidget(self.include_games_count_checkbox)
        
        self.include_games_list_checkbox = QCheckBox("Games List (If Available)")
        self.include_games_list_checkbox.setChecked(False)
        include_fields_layout.addWidget(self.include_games_list_checkbox)
        
        # Add select all checkbox
        self.select_all_fields_checkbox = QCheckBox("Select All Fields")
        self.select_all_fields_checkbox.setChecked(True)
        self.select_all_fields_checkbox.stateChanged.connect(self.toggle_all_fields)
        include_fields_layout.addWidget(self.select_all_fields_checkbox)
        
        include_fields_group.setLayout(include_fields_layout)
        export_layout.addWidget(include_fields_group)
        
        # Export options
        options_layout = QFormLayout()
        
        # Set filename
        filename_layout = QHBoxLayout()
        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("e.g., steam_accounts")
        filename_layout.addWidget(self.filename_input)
        
        # Add timestamp checkbox
        self.add_timestamp_checkbox = QCheckBox("Add Timestamp")
        self.add_timestamp_checkbox.setChecked(True)
        filename_layout.addWidget(self.add_timestamp_checkbox)
        
        options_layout.addRow("Filename:", filename_layout)
        
        export_layout.addLayout(options_layout)
        
        # Export button
        export_button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("Export Results")
        self.export_button.clicked.connect(self.export_filtered_accounts)
        export_button_layout.addWidget(self.export_button)
        
        self.export_only_valid_checkbox = QCheckBox("Export Only Valid Accounts")
        self.export_only_valid_checkbox.setChecked(False)
        export_button_layout.addWidget(self.export_only_valid_checkbox)
        
        export_layout.addLayout(export_button_layout)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Add spacer
        layout.addStretch()
        
        return tab
    
    def create_stats_tab(self):
        """Create tab for statistics"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Statistics
        stats_group = QGroupBox("Account Statistics")
        stats_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                color: #cccccc;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        stats_layout = QVBoxLayout()
        
        # Detailed stats
        self.stats_label = QLabel("No statistics available yet")
        self.stats_label.setStyleSheet("color: #cccccc;")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        stats_layout.addWidget(self.stats_label)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Add spacer
        layout.addStretch()
        
        return tab
    
    def create_status_counter_layout(self, parent_layout):
        """Create status counters layout"""
        # Create status counters (keep existing code)
        status_counter_layout = QHBoxLayout()
        
        self.total_counter_label = QLabel("Total: 0")
        self.total_counter_label.setStyleSheet("color: #cccccc;")
        status_counter_layout.addWidget(self.total_counter_label)
        
        status_counter_layout.addSpacing(15)
        
        self.valid_counter_label = QLabel("Valid: 0")
        self.valid_counter_label.setStyleSheet("color: #55aa55;")
        status_counter_layout.addWidget(self.valid_counter_label)
        
        status_counter_layout.addSpacing(15)
        
        self.error_counter_label = QLabel("Error: 0")
        self.error_counter_label.setStyleSheet("color: #aa5555;")
        status_counter_layout.addWidget(self.error_counter_label)
        
        status_counter_layout.addSpacing(15)
        
        self.steamguard_counter_label = QLabel("SteamGuard: 0")
        self.steamguard_counter_label.setStyleSheet("color: #aaaa55;")
        status_counter_layout.addWidget(self.steamguard_counter_label)
        
        status_counter_layout.addSpacing(15)
        
        self.games_counter_label = QLabel("With Games: 0")
        self.games_counter_label.setStyleSheet("color: #55aaaa;")
        status_counter_layout.addWidget(self.games_counter_label)
        
        status_counter_layout.addStretch()
        
        parent_layout.addLayout(status_counter_layout)
        
    def browse_file(self):
        """Open file dialog to select account file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Account File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            # Validate file path before accepting it
            is_valid, error_msg = validate_file_path(
                file_path, must_exist=True, allowed_extensions=['.txt']
            )
            if not is_valid:
                logger.error(f"Invalid account file selected: {error_msg}")
                QMessageBox.warning(self, "Invalid File", f"Error: {error_msg}")
                return
            
            self.file_path_label.setText(file_path)
            self.check_button.setEnabled(True)
    
    def check_accounts(self):
        """Start checking accounts from the selected file"""
        file_path = self.file_path_label.text()
        
        # Validate file exists
        if file_path == "No file selected" or not file_path:
            QMessageBox.warning(self, "No File Selected", "Please select an account file first.")
            return
        
        # Validate file path
        is_valid, error_msg = validate_file_path(file_path, must_exist=True, allowed_extensions=['.txt'])
        if not is_valid:
            logger.error(f"Invalid account file: {error_msg}")
            QMessageBox.warning(self, "Invalid File", f"Error: {error_msg}")
            return
        
        # Validate thread count
        use_threading = self.use_threading_checkbox.isChecked()
        thread_count = self.thread_count_spinner.value() if use_threading else 1
        
        is_valid, error_msg, validated_count = validate_thread_count(thread_count)
        if not is_valid:
            logger.warning(f"Invalid thread count: {error_msg}")
            thread_count = validated_count
            self.thread_count_spinner.setValue(validated_count)
            QMessageBox.warning(self, "Invalid Thread Count", 
                                f"Thread count adjusted to {validated_count}. {error_msg}")
        
        # Clear previous results
        self.reset_results_table()
        self.reset_counters()
        
        # Update UI state
        self.check_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.browse_button.setEnabled(False)
        self.export_button.setEnabled(False)
        
        # Initialize time tracking
        self.start_time = datetime.datetime.now()
        self.elapsed_label.setText(f"Elapsed: {self.start_time.strftime('%H:%M:%S')}")
        
        # Start the worker thread
        self.checking_worker = AccountCheckWorker(file_path, use_threading, thread_count)
        self.checking_worker.progress_update.connect(self.update_progress)
        self.checking_worker.finished.connect(self.on_checking_finished)
        self.checking_worker.error.connect(self.on_checking_error)
        self.checking_worker.start()
        
    def update_progress(self, current, total, account):
        """Update the progress indicators"""
        # Calculate progress percentage
        progress = int((current / total) * 100)
        
        # Update progress bar
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        
        # Update counters
        self.total_counter_label.setText(f"Total: {total}")
        self.valid_counter_label.setText(f"Valid: {len(self.checking_worker.checker.results[AccountStatus.VALID])}")
        self.error_counter_label.setText(f"Error: {len(self.checking_worker.checker.results[AccountStatus.ERROR])}")
        self.steamguard_counter_label.setText(f"SteamGuard: {len(self.checking_worker.checker.results[AccountStatus.STEAMGUARD])}")
        self.games_counter_label.setText(f"With Games: {len([acc for acc in self.checking_worker.checker.results[AccountStatus.VALID] if len(acc.games) > 0])}")
        
        # Add to the results table
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Username
        username_item = QTableWidgetItem(account.username)
        username_item.setData(Qt.ItemDataRole.UserRole, account)  # Store account object for sorting
        self.results_table.setItem(row, 0, username_item)
        
        # Status
        status_item = QTableWidgetItem(account.status.value)
        status_color = self._get_status_color(account.status)
        status_item.setForeground(QColor(status_color))
        self.results_table.setItem(row, 1, status_item)
        
        # Games
        games_count = len(account.games) if hasattr(account, 'games') and account.games else 0
        games_item = QTableWidgetItem(str(games_count))
        games_item.setData(Qt.ItemDataRole.DisplayRole, games_count)  # For numeric sorting
        self.results_table.setItem(row, 2, games_item)
        
        # Error message / Details
        details = ""
        if account.status == AccountStatus.ERROR and account.error_message:
            details = account.error_message
        elif account.status == AccountStatus.VALID and account.steam_id:
            details = f"Steam ID: {account.steam_id}"
        elif account.status == AccountStatus.STEAMGUARD and account.error_message:
            details = account.error_message
        
        details_item = QTableWidgetItem(details)
        self.results_table.setItem(row, 3, details_item)
        
        # SteamID
        steamid_item = QTableWidgetItem(details)
        self.results_table.setItem(row, 4, steamid_item)
        
        # Scroll to the bottom
        self.results_table.scrollToBottom()
        
    def on_checking_finished(self, results):
        """Handle completion of account checking"""
        logger.info("Account checking completed")
        self.accounts = []
        
        # Store all accounts for filtering
        for status, accounts in results.items():
            for account in accounts:
                self.accounts.append(account)
        
        # Apply filters to show initial results
        self.apply_filters()
        
        # Update summary statistics
        summary = {
            "total": sum(len(accounts) for accounts in results.values()),
            "valid": len(results.get(AccountStatus.VALID, [])),
            "error": len(results.get(AccountStatus.ERROR, [])),
            "steamguard": len(results.get(AccountStatus.STEAMGUARD, [])),
            "with_games": sum(1 for acc in self.accounts if hasattr(acc, 'games') and acc.games)
        }
        
        # Update counters
        self.total_counter_label.setText(f"Total: {summary['total']}")
        self.valid_counter_label.setText(f"Valid: {summary['valid']}")
        self.error_counter_label.setText(f"Error: {summary['error']}")
        self.steamguard_counter_label.setText(f"SteamGuard: {summary['steamguard']}")
        self.games_counter_label.setText(f"With Games: {summary['with_games']}")
        
        # Update progress bar and status
        self.progress_bar.setValue(100)
        self.status_bar.showMessage(f"Check completed: {summary['valid']} valid, {summary['error']} error, {summary['steamguard']} steamguard", 10000)
        
        # Set cursor back to normal
        self.setCursor(Qt.CursorShape.ArrowCursor)
        
        # Cleanup the worker thread
        self.checking_worker = None
        
        # Enable export button if we have results
        if summary['total'] > 0:
            self.export_button.setEnabled(True)
            
        # Change check button text back
        self.check_button.setText("Check Accounts")
        self.check_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def on_checking_error(self, error_message):
        """Handle error during checking process"""
        # Update UI state
        self.check_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # Show error
        self.status_bar.showMessage(f"Error: {error_message}")
        
    def stop_checking(self):
        """Stop the account checking process"""
        if self.checking_worker and self.checking_worker.isRunning():
            self.status_bar.showMessage("Stopping... Please wait")
            
            # First try to gracefully stop the worker
            self.checking_worker.stop()
            
            # Give it a moment to stop gracefully
            success = self.checking_worker.wait(2000)  # Wait up to 2 seconds
            
            if not success:
                # If it doesn't stop gracefully, terminate the thread
                logger.warning("Forcefully terminating worker thread")
                self.checking_worker.terminate()
                self.checking_worker.wait()
            
            # Update UI state
            self.check_button.setEnabled(True)
            self.browse_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
            self.status_bar.showMessage("Account checking stopped")
        
    def export_filtered_accounts(self):
        """Export accounts based on current filters"""
        # Get the currently filtered accounts from the table
        accounts_to_export = []
        for row in range(self.results_table.rowCount()):
            username_item = self.results_table.item(row, 0)
            if username_item:
                # Get the account object from the item's user role data
                account = username_item.data(Qt.ItemDataRole.UserRole)
                if account:
                    accounts_to_export.append(account)
        
        if not accounts_to_export:
            QMessageBox.warning(self, "Export Error", "No accounts to export based on current filter settings.")
            return
            
        # Choose export location
        export_format = self.format_combo.currentText().lower()
        file_extensions = {
            "csv": "CSV Files (*.csv)",
            "json": "JSON Files (*.json)",
            "txt": "Text Files (*.txt)",
            "xml": "XML Files (*.xml)",
            "yaml": "YAML Files (*.yml)"
        }
        extension = file_extensions.get(export_format, "CSV Files (*.csv)")
        
        # Default export directory and filename
        from config.settings import settings
        export_dir = getattr(settings, 'export_dir', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'exports'))
        if not os.path.exists(export_dir):
            try:
                os.makedirs(export_dir)
            except Exception as e:
                logger.error(f"Failed to create export directory: {e}")
                export_dir = os.path.expanduser("~")
                
        # Get custom filename if provided
        custom_filename = self.filename_input.text().strip()
        
        # Create filter description for filename if no custom name provided
        filename_base = custom_filename
        if not filename_base:
            filters = self.filter_frame.get_filters()
            filter_desc = ""
            if filters['status']:
                filter_desc += f"_{filters['status']}"
            if filters['has_games'] is not None:
                filter_desc += f"_{'WithGames' if filters['has_games'] else 'NoGames'}"
            if filters['search']:
                filter_desc += f"_Search-{filters['search'][:10]}"
            
            filename_base = f"accounts{filter_desc}"
        
        # Add timestamp if checkbox is checked
        if self.add_timestamp_checkbox.isChecked():
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            final_filename = f"{filename_base}_{timestamp}.{export_format}"
        else:
            final_filename = f"{filename_base}.{export_format}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Filtered Accounts", 
            os.path.join(export_dir, final_filename),
            extension
        )
        
        if not file_path:
            return
            
        try:
            # Create export options
            export_options = {
                'format': export_format,
                'include_passwords': self.include_password_checkbox.isChecked(),
                'include_steam_ids': self.include_steamid_checkbox.isChecked(),
                'include_games': self.include_games_count_checkbox.isChecked(),
                'include_games_list': self.include_games_list_checkbox.isChecked(),
                'include_email': self.include_email_checkbox.isChecked(),
                'include_status': self.include_status_checkbox.isChecked(),
                'include_username': self.include_username_checkbox.isChecked(),
                'only_valid': self.export_only_valid_checkbox.isChecked()
            }
            
            # Export the accounts
            logger.info(f"Exporting {len(accounts_to_export)} accounts to {file_path}")
            success, count = exporter.export_accounts(accounts_to_export, file_path, export_options)
            
            if success:
                self.status_bar.showMessage(f"Successfully exported {count} accounts to {file_path}", 5000)
                
                # Ask if user wants to open the export file
                reply = QMessageBox.question(
                    self, "Export Complete",
                    f"Successfully exported {count} accounts to {file_path}.\n\nDo you want to open the exported file?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Use the default system application to open the file
                    import subprocess
                    import platform
                    
                    try:
                        if platform.system() == 'Windows':
                            os.startfile(file_path)
                        elif platform.system() == 'Darwin':  # macOS
                            subprocess.call(('open', file_path))
                        else:  # Linux and other Unix-like
                            subprocess.call(('xdg-open', file_path))
                    except Exception as e:
                        logger.error(f"Error opening exported file: {e}")
                        QMessageBox.warning(self, "Error", f"Could not open the exported file: {str(e)}")
            else:
                QMessageBox.warning(self, "Export Error", f"Failed to export accounts: {count}")
                
        except Exception as e:
            logger.error(f"Export error: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{str(e)}")

    def reset_results_table(self):
        """Clear the results table"""
        if hasattr(self, 'results_table') and self.results_table:
            self.results_table.setRowCount(0)
    
    def reset_counters(self):
        """Reset all the counter displays"""
        self.progress_bar.setValue(0)
        self.total_counter_label.setText("Total: 0")
        self.valid_counter_label.setText("Valid: 0")
        self.error_counter_label.setText("Error: 0")
        self.steamguard_counter_label.setText("SteamGuard: 0")
        self.games_counter_label.setText("With Games: 0")
        self.elapsed_label.setText("Elapsed: 00:00:00")

    def apply_filters(self):
        """Apply current filters to the accounts list and update the display"""
        if not hasattr(self, 'accounts') or not self.accounts:
            return
            
        # Get current filter settings
        filters = self.filter_frame.get_filters()
        self.filtered_accounts = []
        
        # Apply filters
        for account in self.accounts:
            # Status filter
            if filters['status'] and account.status.value != filters['status']:
                continue
                
            # Has games filter
            if filters['has_games'] is not None:
                has_games = len(account.games) > 0
                if has_games != filters['has_games']:
                    continue
            
            # Search filter (username or error message)
            if filters['search']:
                search_term = filters['search'].lower()
                username_match = search_term in account.username.lower()
                error_match = account.error_message and search_term in account.error_message.lower()
                
                if not (username_match or error_match):
                    continue
            
            # All filters passed, add to filtered list
            self.filtered_accounts.append(account)
        
        # Update table with filtered results
        self.results_table.setRowCount(0)  # Clear current entries
        self.results_table.setSortingEnabled(False)  # Disable sorting while updating
        
        # Add filtered accounts to table
        for account in self.filtered_accounts:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            
            # Username
            username_item = QTableWidgetItem(account.username)
            username_item.setData(Qt.ItemDataRole.UserRole, account)  # Store account object for sorting
            self.results_table.setItem(row, 0, username_item)
            
            # Status
            status_item = QTableWidgetItem(account.status.value)
            status_color = self._get_status_color(account.status)
            status_item.setForeground(QColor(status_color))
            self.results_table.setItem(row, 1, status_item)
            
            # Games
            games_count = len(account.games) if hasattr(account, 'games') and account.games else 0
            games_item = QTableWidgetItem(str(games_count))
            games_item.setData(Qt.ItemDataRole.DisplayRole, games_count)  # For numeric sorting
            self.results_table.setItem(row, 2, games_item)
            
            # Error message / Details
            details = ""
            if account.status == AccountStatus.ERROR and account.error_message:
                details = account.error_message
            elif account.status == AccountStatus.VALID and account.steam_id:
                details = f"Steam ID: {account.steam_id}"
            elif account.status == AccountStatus.STEAMGUARD and account.error_message:
                details = account.error_message
                
            details_item = QTableWidgetItem(details)
            self.results_table.setItem(row, 3, details_item)
            
            # SteamID
            steamid_item = QTableWidgetItem(details)
            self.results_table.setItem(row, 4, steamid_item)
        
        # Re-enable sorting and apply sort settings
        self.results_table.setSortingEnabled(True)
        if filters['sort_column'] is not None:
            self.results_table.sortItems(filters['sort_column'], filters['sort_order'])
        
        # Update the filter status
        filter_count = len(self.filtered_accounts)
        total_count = len(self.accounts)
        if filter_count < total_count:
            self.status_bar.showMessage(f"Showing {filter_count} of {total_count} accounts (filtered)")
        else:
            self.status_bar.showMessage(f"Showing all {total_count} accounts")
    
    def _get_status_color(self, status):
        """Get the color for a given account status"""
        if status == AccountStatus.VALID:
            return "#00cc00"  # Green
        elif status == AccountStatus.ERROR:
            return "#cc0000"  # Red
        elif status == AccountStatus.STEAMGUARD:
            return "#cccc00"  # Yellow
        else:
            return "#cccccc"  # Default gray

    def toggle_all_fields(self, state):
        """Toggle the state of all fields in the include fields group"""
        include_fields_group = self.export_tab.findChild(QGroupBox, "Fields to Include")
        if include_fields_group:
            for i in range(include_fields_group.layout().count()):
                widget = include_fields_group.layout().itemAt(i).widget()
                if isinstance(widget, QCheckBox):
                    widget.setChecked(state == Qt.CheckState.Checked)
