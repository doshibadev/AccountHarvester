"""
Main application window for AccountHarvester
"""
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget,
    QShortcut, QApplication
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QKeySequence

from ui.manual_tab import ManualTab
from ui.automatic_tab import AutomaticTab
from ui.settings_tab import SettingsTab
from ui.help_tab import HelpTab
from core.proxy_manager import proxy_manager
from utils.logger import logger

class MainWindow(QMainWindow):
    """Main application window with tabbed interface"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("AccountHarvester - Steam Account Checker")
        self.setMinimumSize(800, 600)
        
        # Create central widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Create tabs
        self.manual_tab = ManualTab()
        self.automatic_tab = AutomaticTab()
        self.settings_tab = SettingsTab()
        self.help_tab = HelpTab()
        
        # Add tabs to tab widget
        self.tabs.addTab(self.manual_tab, "Manual Check")
        self.tabs.addTab(self.automatic_tab, "Automatic Check")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.help_tab, "Help")
        
        # Connect signals
        self.settings_tab.settings_updated.connect(self.on_settings_updated)
        
        # Setup keyboard shortcuts
        self.setup_shortcuts()
        
    def setup_shortcuts(self):
        """Setup keyboard shortcuts for the application"""
        # Tab switching shortcuts
        self.shortcut_tab1 = QShortcut(QKeySequence("Ctrl+1"), self)
        self.shortcut_tab1.activated.connect(lambda: self.tabs.setCurrentIndex(0))  # Manual Tab
        
        self.shortcut_tab2 = QShortcut(QKeySequence("Ctrl+2"), self)
        self.shortcut_tab2.activated.connect(lambda: self.tabs.setCurrentIndex(1))  # Automatic Tab
        
        self.shortcut_tab3 = QShortcut(QKeySequence("Ctrl+3"), self)
        self.shortcut_tab3.activated.connect(lambda: self.tabs.setCurrentIndex(2))  # Settings Tab
        
        self.shortcut_tab4 = QShortcut(QKeySequence("Ctrl+4"), self)
        self.shortcut_tab4.activated.connect(lambda: self.tabs.setCurrentIndex(3))  # Help Tab
        
        # Action shortcuts
        
        # Manual tab shortcuts - Check Account with Enter
        self.shortcut_check_account = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut_check_account.activated.connect(self.trigger_check_account)
        
        # Automatic tab shortcuts - Use standard key sequences where possible
        self.shortcut_browse_file = QShortcut(QKeySequence.StandardKey.Open, self)  # Ctrl+O or Command+O
        self.shortcut_browse_file.activated.connect(self.trigger_browse_file)
        
        self.shortcut_start_checking = QShortcut(QKeySequence("Ctrl+R"), self)
        self.shortcut_start_checking.activated.connect(self.trigger_start_checking)
        
        # Stop checking with Ctrl+S (note: conflicts with Save in some programs)
        self.shortcut_stop_checking = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_stop_checking.activated.connect(self.trigger_stop_checking)
        
        # Export with Ctrl+E
        self.shortcut_export = QShortcut(QKeySequence("Ctrl+E"), self)
        self.shortcut_export.activated.connect(self.trigger_export_results)
        
        # Settings tab shortcuts - Save settings with Ctrl+Shift+S
        self.shortcut_save_settings = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.shortcut_save_settings.activated.connect(self.trigger_save_settings)
        
        # Application quit with platform-specific shortcut
        self.shortcut_quit = QShortcut(QKeySequence.StandardKey.Quit, self)
        self.shortcut_quit.activated.connect(QApplication.instance().quit)
        
    def trigger_check_account(self):
        """Trigger the check account action in the manual tab"""
        if self.tabs.currentIndex() == 0:  # Manual tab is active
            if hasattr(self.manual_tab, 'check_account'):
                self.manual_tab.check_account()
    
    def trigger_browse_file(self):
        """Trigger the browse file action in the automatic tab"""
        if self.tabs.currentIndex() == 1:  # Automatic tab is active
            if hasattr(self.automatic_tab, 'browse_file'):
                self.automatic_tab.browse_file()
    
    def trigger_start_checking(self):
        """Trigger the start checking action in the automatic tab"""
        if self.tabs.currentIndex() == 1:  # Automatic tab is active
            if hasattr(self.automatic_tab, 'check_accounts') and hasattr(self.automatic_tab, 'check_button') and self.automatic_tab.check_button.isEnabled():
                self.automatic_tab.check_accounts()
    
    def trigger_stop_checking(self):
        """Trigger the stop checking action in the automatic tab"""
        if self.tabs.currentIndex() == 1:  # Automatic tab is active
            if hasattr(self.automatic_tab, 'stop_checking') and hasattr(self.automatic_tab, 'stop_button') and self.automatic_tab.stop_button.isEnabled():
                self.automatic_tab.stop_checking()
    
    def trigger_export_results(self):
        """Trigger the export results action in the automatic tab"""
        if self.tabs.currentIndex() == 1:  # Automatic tab is active
            if hasattr(self.automatic_tab, 'export_filtered_accounts'):
                self.automatic_tab.export_filtered_accounts()
    
    def trigger_save_settings(self):
        """Trigger the save settings action in the settings tab"""
        if self.tabs.currentIndex() == 2:  # Settings tab is active
            if hasattr(self.settings_tab, 'save_settings'):
                self.settings_tab.save_settings()
        
    def on_settings_updated(self):
        """Handle settings updates"""
        # Propagate settings changes to other tabs
        pass
    
    def closeEvent(self, event):
        """Handle closing the application"""
        try:
            # Clean up proxy connection pools
            logger.info("Cleaning up resources before application exit")
            proxy_manager.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup on application exit: {str(e)}", exc_info=True)
        
        # Accept the close event
        event.accept()
