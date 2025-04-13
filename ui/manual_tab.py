"""
Manual tab for checking individual accounts
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFormLayout, QGroupBox,
    QTextEdit, QStatusBar, QMessageBox, QProgressBar,
    QFrame, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QColor, QFont
from core.account import SteamAccount, AccountStatus
from utils.input_validation import validate_credentials, sanitize_input
from utils.logger import logger
import time

class AccountCheckThread(QThread):
    """Thread for checking a single account"""
    status_update = pyqtSignal(str)
    progress_update = pyqtSignal(str, int)  # Message, progress percentage
    finished = pyqtSignal(SteamAccount)
    error = pyqtSignal(str)
    
    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password
        
    def run(self):
        """Run the account check"""
        try:
            # Step 1: Initializing
            self.progress_update.emit("Initializing check...", 10)
            time.sleep(0.5)  # Small delay for UI feedback
            
            # Step 2: Connect to Steam
            self.progress_update.emit("Connecting to Steam...", 30)
            
            # Create the account directly instead of using from_credentials_line 
            # since we've already validated the inputs
            account = SteamAccount(self.username, self.password)
            
            # Step 3: Authentication
            self.progress_update.emit("Authenticating credentials...", 50)
            status = account.check_account()
            
            # Step 4: Processing results
            self.progress_update.emit("Processing login results...", 75)
            
            # Step 5: Additional information
            if status == AccountStatus.VALID:
                self.progress_update.emit("Account is valid! Fetching games...", 85)
                account.fetch_owned_games()
                self.progress_update.emit("Completed", 100)
            else:
                self.progress_update.emit("Completed", 100)
            
            self.finished.emit(account)
        except Exception as e:
            self.progress_update.emit("Error occurred", 100)
            logger.error(f"Error in account check thread: {str(e)}", exc_info=True)
            self.error.emit(f"Error checking account: {str(e)}")

class ManualTab(QWidget):
    """Tab for manually checking individual accounts"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.check_thread = None
        
    def setup_ui(self):
        """Set up the user interface with nested tabs"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Input section (always visible at the top)
        self.create_input_section(main_layout)
        
        # Create nested tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs for different sections
        self.status_tab = self.create_status_tab()
        self.details_tab = self.create_details_tab()
        self.games_tab = self.create_games_tab()
        
        # Add tabs to tab widget
        self.tab_widget.addTab(self.status_tab, "Status")
        self.tab_widget.addTab(self.details_tab, "Details")
        self.tab_widget.addTab(self.games_tab, "Games")
        
        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)
        
        # Status bar (always visible at the bottom)
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        main_layout.addWidget(self.status_bar)
        
    def create_input_section(self, parent_layout):
        """Create the input section with credentials form"""
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
        
        # Input section
        input_group = QGroupBox("Account Credentials")
        input_group.setStyleSheet(group_box_style)
        input_layout = QVBoxLayout()
        
        # Form layout for credentials
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Steam username")
        self.username_input.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555; padding: 5px;")
        form_layout.addRow(QLabel("Username:"), self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Steam password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet("background-color: #2d2d2d; color: #ffffff; border: 1px solid #555555; padding: 5px;")
        form_layout.addRow(QLabel("Password:"), self.password_input)
        
        # Style form labels
        for i in range(form_layout.rowCount()):
            label_item = form_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setStyleSheet("color: #cccccc;")
        
        input_layout.addLayout(form_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        button_style = "background-color: #2d2d2d; color: #ffffff; padding: 6px; border: 1px solid #555555;"
        
        self.check_button = QPushButton("Check Account")
        self.check_button.clicked.connect(self.check_account)
        self.check_button.setStyleSheet(button_style)
        button_layout.addWidget(self.check_button)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_inputs)
        self.clear_button.setStyleSheet(button_style)
        button_layout.addWidget(self.clear_button)
        
        input_layout.addLayout(button_layout)
        
        # Progress bar
        progress_layout = QVBoxLayout()
        
        self.step_label = QLabel("Waiting to start...")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_label.setStyleSheet("color: #cccccc;")
        progress_layout.addWidget(self.step_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p% - %v")
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("QProgressBar {text-align: center; border: 1px solid #555555; border-radius: 3px; background: #1a1a1a; color: white;} "
                                       "QProgressBar::chunk {background-color: #0066cc;}")
        progress_layout.addWidget(self.progress_bar)
        
        input_layout.addLayout(progress_layout)
        
        input_group.setLayout(input_layout)
        parent_layout.addWidget(input_group)
    
    def create_status_tab(self):
        """Create tab for account status information"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Status information
        status_group = QGroupBox("Account Status")
        status_group.setStyleSheet("""
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
        status_layout = QVBoxLayout()
        
        # Status display with better styling
        status_frame = QFrame()
        status_frame.setFrameShape(QFrame.Shape.StyledPanel)
        status_frame.setFrameShadow(QFrame.Shadow.Raised)
        status_frame.setStyleSheet("background-color: #2d2d2d; border-radius: 5px;")
        status_frame_layout = QHBoxLayout(status_frame)
        
        status_label = QLabel("Status:")
        status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        status_frame_layout.addWidget(status_label)
        
        self.status_label = QLabel("Not checked")
        self.status_label.setStyleSheet("font-weight: bold; color: #aaaaaa; font-size: 14px;")
        status_frame_layout.addWidget(self.status_label)
        
        # Steam ID display (shown when available)
        status_frame_layout.addStretch()
        
        self.steamid_label = QLabel()
        self.steamid_label.setVisible(False)
        self.steamid_label.setStyleSheet("color: #55aaff; font-style: italic;")
        status_frame_layout.addWidget(self.steamid_label)
        
        status_layout.addWidget(status_frame)
        
        # Time tracking
        time_layout = QHBoxLayout()
        
        self.elapsed_time_label = QLabel("Time elapsed: 0.0 seconds")
        self.elapsed_time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.elapsed_time_label.setStyleSheet("color: #cccccc;")
        time_layout.addWidget(self.elapsed_time_label)
        
        status_layout.addLayout(time_layout)
        
        # Basic info layout
        basic_info_layout = QFormLayout()
        
        self.username_result_label = QLabel("-")
        self.username_result_label.setStyleSheet("color: #cccccc;")
        basic_info_layout.addRow(QLabel("Username:"), self.username_result_label)
        
        self.email_label = QLabel("-")
        self.email_label.setStyleSheet("color: #cccccc;")
        basic_info_layout.addRow(QLabel("Email:"), self.email_label)
        
        self.steamid_result_label = QLabel("-")
        self.steamid_result_label.setStyleSheet("color: #cccccc;")
        basic_info_layout.addRow(QLabel("Steam ID:"), self.steamid_result_label)
        
        self.profile_link_label = QLabel("-")
        self.profile_link_label.setStyleSheet("color: #55aaff;")
        self.profile_link_label.setOpenExternalLinks(True)
        basic_info_layout.addRow(QLabel("Profile:"), self.profile_link_label)
        
        # Style form labels
        for i in range(basic_info_layout.rowCount()):
            label_item = basic_info_layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setStyleSheet("color: #aaaaaa;")
        
        status_layout.addLayout(basic_info_layout)
        
        # Error message if applicable
        self.error_message_label = QLabel("")
        self.error_message_label.setStyleSheet("color: #ff5555;")
        self.error_message_label.setWordWrap(True)
        self.error_message_label.setVisible(False)
        status_layout.addWidget(self.error_message_label)
        
        status_layout.addStretch()
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        return tab
    
    def create_details_tab(self):
        """Create tab for detailed account information"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Details section
        details_group = QGroupBox("Account Details")
        details_group.setStyleSheet("""
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
        details_layout = QVBoxLayout()
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setPlaceholderText("Account details will appear here")
        self.details_text.setStyleSheet("background-color: #1e1e1e; color: #f0f0f0; border: 1px solid #444444;")
        details_layout.addWidget(self.details_text)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        return tab
    
    def create_games_tab(self):
        """Create tab for games information"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Games section
        games_group = QGroupBox("Owned Games")
        games_group.setStyleSheet("""
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
        games_layout = QVBoxLayout()
        
        # Game count display
        count_frame = QFrame()
        count_frame.setFrameShape(QFrame.Shape.StyledPanel)
        count_frame.setFrameShadow(QFrame.Shadow.Raised)
        count_frame.setStyleSheet("background-color: #2d2d2d; border-radius: 5px;")
        count_layout = QHBoxLayout(count_frame)
        
        self.games_count_label = QLabel("Games: 0")
        self.games_count_label.setStyleSheet("font-weight: bold; color: #55aaff; font-size: 14px;")
        count_layout.addWidget(self.games_count_label)
        
        games_layout.addWidget(count_frame)
        
        # Games list
        self.games_text = QTextEdit()
        self.games_text.setReadOnly(True)
        self.games_text.setPlaceholderText("Games list will appear here after account check")
        self.games_text.setStyleSheet("background-color: #1e1e1e; color: #f0f0f0; border: 1px solid #444444;")
        games_layout.addWidget(self.games_text)
        
        games_group.setLayout(games_layout)
        layout.addWidget(games_group)
        
        return tab
    
    def check_account(self):
        """Check the entered Steam account"""
        # Get and validate credentials
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            self.status_bar.showMessage("Please enter both username and password")
            return
        
        # Validate credentials
        is_valid, error_msg, _ = validate_credentials(f"{username}:{password}")
        if not is_valid:
            self.status_bar.showMessage(f"Invalid credentials: {error_msg}")
            return
        
        # Disable controls during check
        self.check_button.setDisabled(True)
        self.username_input.setDisabled(True)
        self.password_input.setDisabled(True)
        
        # Reset UI
        self.progress_bar.setValue(0)
        self.step_label.setText("Starting check...")
        self.status_label.setText("Checking...")
        self.status_label.setStyleSheet("font-weight: bold; color: #ffaa00; font-size: 14px;")
        self.steamid_label.setVisible(False)
        self.details_text.clear()
        self.games_text.clear()
        self.games_count_label.setText("Games: 0")
        self.error_message_label.setVisible(False)
        
        # Set up elapsed time timer
        self.start_time = time.time()
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self.update_elapsed_time)
        self.elapsed_timer.start(100)  # Update every 100ms
        
        # Create and start the worker thread
        self.check_thread = AccountCheckThread(username, password)
        self.check_thread.status_update.connect(self.update_status)
        self.check_thread.progress_update.connect(self.update_progress)
        self.check_thread.finished.connect(self.on_check_completed)
        self.check_thread.error.connect(self.on_check_error)
        self.check_thread.start()
        
        self.status_bar.showMessage(f"Checking account: {username}")
    
    def update_status(self, message):
        """Update the status display"""
        self.status_bar.showMessage(message)
    
    def update_progress(self, message, percentage):
        """Update the progress display"""
        self.step_label.setText(message)
        self.progress_bar.setValue(percentage)
    
    def update_elapsed_time(self):
        """Update the elapsed time display"""
        elapsed = time.time() - self.start_time
        self.elapsed_time_label.setText(f"Time elapsed: {elapsed:.1f} seconds")
    
    def on_check_error(self, error_message):
        """Handle error during account check"""
        # Stop the timer
        if self.elapsed_timer and self.elapsed_timer.isActive():
            self.elapsed_timer.stop()
        
        # Update UI
        self.check_button.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        
        self.status_label.setText("Error")
        self.status_label.setStyleSheet("font-weight: bold; color: #ff5555; font-size: 14px;")
        
        # Show error details
        self.error_message_label.setText(error_message)
        self.error_message_label.setVisible(True)
        
        # Update status bar
        self.status_bar.showMessage(f"Error: {error_message}")
    
    def on_check_completed(self, account):
        """Handle completion of account check"""
        # Stop the timer
        if self.elapsed_timer and self.elapsed_timer.isActive():
            self.elapsed_timer.stop()
        
        # Re-enable controls
        self.check_button.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        
        # Update status indicator
        if account.status == AccountStatus.VALID:
            self.status_label.setText("Valid")
            self.status_label.setStyleSheet("font-weight: bold; color: #55aa55; font-size: 14px;")
            
            if account.steam_id:
                # Show Steam ID
                self.steamid_label.setText(f"SteamID: {account.steam_id}")
                self.steamid_label.setVisible(True)
                
                # Update SteamID in details tab
                self.steamid_result_label.setText(str(account.steam_id))
                
                # Add profile link
                profile_url = f"https://steamcommunity.com/profiles/{account.steam_id}"
                self.profile_link_label.setText(f"<a href='{profile_url}'>{profile_url}</a>")
            
            # Switch to the status tab
            self.tab_widget.setCurrentIndex(0)
        elif account.status == AccountStatus.STEAMGUARD:
            self.status_label.setText("SteamGuard")
            self.status_label.setStyleSheet("font-weight: bold; color: #ffaa00; font-size: 14px;")
        else:
            self.status_label.setText("Invalid")
            self.status_label.setStyleSheet("font-weight: bold; color: #ff5555; font-size: 14px;")
            
            # Show error message
            if account.error_message:
                self.error_message_label.setText(account.error_message)
                self.error_message_label.setVisible(True)
        
        # Update username in status tab
        self.username_result_label.setText(account.username)
        
        # Populate details text
        details = self.format_account_details(account)
        self.details_text.setHtml(details)
        
        # Update games tab
        if hasattr(account, 'games') and account.games:
            self.games_count_label.setText(f"Games: {len(account.games)}")
            
            # Create formatted games list
            games_html = "<style>body { color: #cccccc; } .game { margin-bottom: 6px; }</style>"
            games_html += "<h3>Owned Games:</h3>"
            
            for game in sorted(account.games, key=lambda g: g.get('name', '')):
                name = game.get('name', 'Unknown Game')
                app_id = game.get('appid', 'N/A')
                playtime = game.get('playtime_forever', 0)
                
                playtime_str = ""
                if playtime > 0:
                    hours = playtime // 60
                    minutes = playtime % 60
                    if hours > 0:
                        playtime_str = f" - {hours}h {minutes}m playtime"
                    else:
                        playtime_str = f" - {minutes}m playtime"
                
                games_html += f"<div class='game'><b>{name}</b> (AppID: {app_id}){playtime_str}</div>"
            
            self.games_text.setHtml(games_html)
        else:
            self.games_text.setPlainText("No games found or not logged in.")
        
        # Update status bar
        self.status_bar.showMessage(f"Account check completed: {account.status.value}")
    
    def format_account_details(self, account):
        """Format account details as HTML for display"""
        html = "<style>body {color: #cccccc; font-family: Arial, sans-serif;}</style>"
        html += f"<h3>Account Information</h3>"
        html += f"<p><b>Username:</b> {account.username}</p>"
        html += f"<p><b>Status:</b> <span style='color: {self._get_status_color(account.status)};'>{account.status.value}</span></p>"
        
        if account.steam_id:
            html += f"<p><b>Steam ID:</b> {account.steam_id}</p>"
            html += f"<p><b>Profile:</b> <a href='https://steamcommunity.com/profiles/{account.steam_id}'>https://steamcommunity.com/profiles/{account.steam_id}</a></p>"
        
        if account.error_code:
            html += f"<p><b>Error Code:</b> {account.error_code}</p>"
        
        if account.error_message:
            html += f"<p><b>Error Message:</b> <span style='color: #ff5555;'>{account.error_message}</span></p>"
        
        return html
    
    def _get_status_color(self, status):
        """Get color for account status"""
        if status == AccountStatus.VALID:
            return "#55aa55"  # Green
        elif status == AccountStatus.STEAMGUARD:
            return "#ffaa00"  # Orange
        else:
            return "#ff5555"  # Red
    
    def clear_inputs(self):
        """Clear all input fields and reset display"""
        self.username_input.clear()
        self.password_input.clear()
        self.status_label.setText("Not checked")
        self.status_label.setStyleSheet("font-weight: bold; color: #aaaaaa; font-size: 14px;")
        self.steamid_label.setVisible(False)
        self.details_text.clear()
        self.progress_bar.setValue(0)
        self.step_label.setText("Waiting to start...")
        self.error_message_label.setVisible(False)
        
        # Reset other labels
        self.username_result_label.setText("-")
        self.email_label.setText("-")
        self.steamid_result_label.setText("-")
        self.profile_link_label.setText("-")
        self.games_count_label.setText("Games: 0")
        self.games_text.clear()
        
        self.status_bar.showMessage("Ready")
