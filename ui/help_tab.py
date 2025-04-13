"""
Help tab for providing documentation and assistance
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTabWidget, QTextBrowser, QGroupBox, QPushButton,
    QScrollArea
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
import os
from config.settings import settings

class HelpTab(QWidget):
    """Tab for providing documentation and assistance"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface"""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Help tabs
        help_tabs = QTabWidget()
        layout.addWidget(help_tabs)
        
        # About tab
        about_widget = QWidget()
        about_layout = QVBoxLayout(about_widget)
        
        about_text = QTextBrowser()
        about_text.setOpenExternalLinks(True)
        about_text.setHtml("""
            <h1>AccountHarvester</h1>
            <p>Version 1.1</p>
            <p>AccountHarvester is a tool for checking the validity of Steam accounts and retrieving information about owned games.</p>
            <p>This application is for educational purposes only. Use responsibly and only with accounts you own or have permission to check.</p>
            
            <h2>Features</h2>
            <ul>
                <li>Check individual or multiple Steam accounts</li>
                <li>Retrieve owned games and account details</li>
                <li>Support for proxy connections to avoid rate limiting</li>
                <li>Multi-threaded processing for faster checking</li>
                <li>Export results to multiple formats (CSV, JSON, TXT, XML, YAML)</li>
                <li>Detailed error reporting and status tracking</li>
                <li>Configuration backup and restore</li>
                <li>Cleanup utilities for cache, logs, and export files</li>
                <li>Organized user interface with nested tabs</li>
            </ul>
        """)
        about_layout.addWidget(about_text)
        
        help_tabs.addTab(about_widget, "About")
        
        # Usage tab
        usage_widget = QWidget()
        usage_layout = QVBoxLayout(usage_widget)
        
        usage_text = QTextBrowser()
        usage_text.setHtml("""
            <h1>How to Use</h1>
            
            <h2>Manual Checking</h2>
            <p>Use the Manual Check tab to check individual accounts:</p>
            <ol>
                <li>Enter a Steam username and password in the input fields</li>
                <li>Click "Check Account" to verify the account</li>
                <li>Results will be displayed in three tabs:
                    <ul>
                        <li><strong>Status</strong>: Shows account validity status, basic info, and profile link</li>
                        <li><strong>Details</strong>: Shows detailed account information</li>
                        <li><strong>Games</strong>: Shows owned games with playtime statistics (if applicable)</li>
                    </ul>
                </li>
                <li>If valid and you have an API key configured, owned games will be displayed in the Games tab</li>
            </ol>
            
            <h2>Automatic Checking</h2>
            <p>Use the Automatic Check tab to check multiple accounts from a file:</p>
            <ol>
                <li>Click the "Browse" button to select a file containing accounts</li>
                <li>The file should contain one account per line in the format <code>username:password</code></li>
                <li>Configure threading options if needed</li>
                <li>Click "Check Accounts" to start the checking process</li>
                <li>Progress will be shown along with a summary of results</li>
                <li>After checking, use the different tabs to:
                    <ul>
                        <li><strong>Results</strong>: View and sort the results in a table</li>
                        <li><strong>Filters & Sorting</strong>: Filter accounts by status, games, and other criteria</li>
                        <li><strong>Export</strong>: Export results to various formats with custom options</li>
                        <li><strong>Statistics</strong>: View detailed statistics about the checked accounts</li>
                    </ul>
                </li>
            </ol>
            
            <h2>Settings</h2>
            <p>Configure application settings in the Settings tab:</p>
            <ol>
                <li>Navigate through the nested tabs to access different settings:
                    <ul>
                        <li><strong>API Settings</strong>: Configure Steam API key for game retrieval</li>
                        <li><strong>Performance</strong>: Adjust thread count and other performance settings</li>
                        <li><strong>Proxy Settings</strong>: Configure proxy connections</li>
                        <li><strong>Cache Settings</strong>: Manage application cache</li>
                        <li><strong>Backup & Restore</strong>: Create and manage configuration backups</li>
                    </ul>
                </li>
                <li>Click "Save Settings" to apply changes</li>
            </ol>
            
            <h2>Export Options</h2>
            <p>Export your results with various options:</p>
            <ol>
                <li>Select from multiple export formats:
                    <ul>
                        <li><strong>CSV</strong>: Standard comma-separated values file</li>
                        <li><strong>TXT</strong>: Readable text format</li>
                        <li><strong>JSON</strong>: Structured data format for programmatic use</li>
                        <li><strong>XML</strong>: Extended markup language format</li>
                        <li><strong>YAML</strong>: Human-readable structured data format</li>
                    </ul>
                </li>
                <li>Choose which fields to include in the export</li>
                <li>Provide a custom filename or use the automatically generated one</li>
                <li>Optionally add timestamps to filenames</li>
                <li>Filter exports to include only valid accounts</li>
            </ol>
            
            <h2>Backup & Restore</h2>
            <p>Manage your application configuration:</p>
            <ol>
                <li>Create backups of your settings to preserve your configuration</li>
                <li>Restore from previously created backups if needed</li>
                <li>Manage backup files directly from the interface</li>
            </ol>
            
            <h2>Cleanup Utilities</h2>
            <p>Maintain your application's performance and storage:</p>
            <ol>
                <li>Clear cache files to free up disk space</li>
                <li>Clean up old log files</li>
                <li>Remove temporary export files</li>
                <li>Schedule automatic cleanups or run them manually</li>
            </ol>
            
            <h2>Command Line Usage</h2>
            <p>AccountHarvester can also be used from the command line:</p>
            <pre>
# Check a single account
python run.py check username:password

# Check accounts from a file
python run.py file path/to/accounts.txt --export

# Check accounts without threading
python run.py file path/to/accounts.txt --no-threading

# Clean up cache, logs, and exports
python run.py cleanup --all
python run.py cleanup --cache --logs

# Backup and restore configuration
python run.py backup --create
python run.py backup --restore 1
python run.py backup --list

# Launch GUI (default)
python run.py
            </pre>
        """)
        usage_layout.addWidget(usage_text)
        
        help_tabs.addTab(usage_widget, "Usage")
        
        # Error Codes tab
        error_codes_widget = QWidget()
        error_codes_layout = QVBoxLayout(error_codes_widget)
        
        error_codes_text = QTextBrowser()
        error_codes_text.setHtml("""
            <h1>Steam Error Codes</h1>
            <p>This section explains the Steam error codes you may encounter:</p>
            
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr>
                    <th>Error Code</th>
                    <th>Message</th>
                    <th>Description</th>
                </tr>
                <tr>
                    <td>5</td>
                    <td>InvalidPassword</td>
                    <td>The password you entered is incorrect.</td>
                </tr>
                <tr>
                    <td>7</td>
                    <td>AccountNotFound</td>
                    <td>The account name doesn't exist in Steam's database.</td>
                </tr>
                <tr>
                    <td>14</td>
                    <td>InvalidName</td>
                    <td>The account name entered is not valid.</td>
                </tr>
                <tr>
                    <td>18</td>
                    <td>AccountDisabled</td>
                    <td>The account has been disabled by Steam support.</td>
                </tr>
                <tr>
                    <td>63</td>
                    <td>AccountLogonDenied</td>
                    <td>Account requires SteamGuard email code verification.</td>
                </tr>
                <tr>
                    <td>84</td>
                    <td>AccountLoginDeniedNeedTwoFactor</td>
                    <td>Account requires mobile authenticator code (2FA).</td>
                </tr>
                <tr>
                    <td>50</td>
                    <td>ServiceUnavailable</td>
                    <td>Steam services are unavailable. <strong>In AccountHarvester, accounts with this error are classified as VALID</strong> since the credentials are correct but Steam is temporarily unavailable.</td>
                </tr>
                <tr>
                    <td>24</td>
                    <td>IPBanned</td>
                    <td>Your IP address has been temporarily banned by Steam.</td>
                </tr>
                <tr>
                    <td>73</td>
                    <td>RateLimitExceeded</td>
                    <td>Too many login attempts in a short period.</td>
                </tr>
                <tr>
                    <td>65</td>
                    <td>LimitExceeded</td>
                    <td>Account has exceeded login limit.</td>
                </tr>
                <tr>
                    <td>29</td>
                    <td>Timeout</td>
                    <td>Connection to Steam servers timed out.</td>
                </tr>
            </table>
            
            <h2>Special Cases</h2>
            <p><strong>Error 50 (Service Unavailable)</strong>: In AccountHarvester, this error is treated as a VALID account and will appear in the Valid accounts list and exports. It usually means the credentials are correct, but Steam is temporarily blocking login attempts. This is a common response when checking multiple accounts in succession.</p>
            
            <p><strong>Error Codes 63 and 84</strong>: These indicate the account credentials are correct, but the account is protected by SteamGuard or two-factor authentication.</p>
            
            <p><strong>Error Codes 73 and 65</strong>: These rate limiting errors suggest you should use proxies or reduce the frequency of login attempts.</p>
        """)
        error_codes_layout.addWidget(error_codes_text)
        
        help_tabs.addTab(error_codes_widget, "Error Codes")
        
        # Troubleshooting tab
        troubleshooting_widget = QWidget()
        troubleshooting_layout = QVBoxLayout(troubleshooting_widget)
        
        troubleshooting_text = QTextBrowser()
        troubleshooting_text.setHtml("""
            <h1>Troubleshooting</h1>
            
            <h2>Account Statuses</h2>
            <ul>
                <li><strong>Valid</strong>: The account credentials are correct and the account is accessible</li>
                <li><strong>SteamGuard</strong>: The account is protected by SteamGuard and requires additional authentication</li>
                <li><strong>Error</strong>: The account credentials are incorrect or there was an error during login</li>
            </ul>
            
            <h2>Common Issues</h2>
            
            <h3>Connection Issues</h3>
            <ul>
                <li><strong>Problem</strong>: Failed to connect to Steam servers<br>
                    <strong>Solution</strong>: Check your internet connection, try using a proxy, or wait and try again later</li>
                <li><strong>Problem</strong>: Timeout errors<br>
                    <strong>Solution</strong>: Increase the connection timeout in settings, or use a more reliable network</li>
                <li><strong>Problem</strong>: Rate limiting errors<br>
                    <strong>Solution</strong>: Reduce thread count, use proxies, or add delays between checks</li>
            </ul>
            
            <h3>API Issues</h3>
            <ul>
                <li><strong>Problem</strong>: Games not loading<br>
                    <strong>Solution</strong>: Verify your API key is valid and properly entered in settings</li>
                <li><strong>Problem</strong>: API key validation fails<br>
                    <strong>Solution</strong>: Get a new API key from <a href="https://steamcommunity.com/dev/apikey">Steam's API Key page</a></li>
                <li><strong>Problem</strong>: Some accounts show no games<br>
                    <strong>Solution</strong>: The account may have a private profile or no games</li>
            </ul>
            
            <h3>Proxy Issues</h3>
            <ul>
                <li><strong>Problem</strong>: Proxies not working<br>
                    <strong>Solution</strong>: Ensure proxies are in the correct format (ip:port or ip:port:user:pass)</li>
                <li><strong>Problem</strong>: Slow performance with proxies<br>
                    <strong>Solution</strong>: This is normal; proxy connections are typically slower than direct connections</li>
                <li><strong>Problem</strong>: All proxies failing<br>
                    <strong>Solution</strong>: Your proxies may be banned by Steam or inactive; try new proxies</li>
            </ul>
            
            <h3>File Format Issues</h3>
            <ul>
                <li><strong>Problem</strong>: No accounts found in file<br>
                    <strong>Solution</strong>: Ensure your file uses the format "username:password" with one account per line</li>
                <li><strong>Problem</strong>: Export fails<br>
                    <strong>Solution</strong>: Check if the destination directory is writable</li>
            </ul>
            
            <h2>Performance Tips</h2>
            <ul>
                <li>For optimal performance, set thread count to match your CPU cores (usually 4-8)</li>
                <li>When using proxies, increase thread count to compensate for slower connections</li>
                <li>Checking large numbers of accounts (1000+) may require breaking into smaller batches</li>
                <li>Clearing the API cache periodically can help with memory usage</li>
            </ul>
        """)
        troubleshooting_layout.addWidget(troubleshooting_text)
        
        help_tabs.addTab(troubleshooting_widget, "Troubleshooting")
        
        # FAQ tab
        faq_widget = QWidget()
        faq_layout = QVBoxLayout(faq_widget)
        
        faq_text = QTextBrowser()
        faq_text.setHtml("""
            <h1>Frequently Asked Questions</h1>
            
            <h3>Q: What is AccountHarvester?</h3>
            <p>A: AccountHarvester is a tool for checking the validity of Steam accounts and retrieving information about owned games. It can be used to verify account credentials and obtain basic account information.</p>
            
            <h3>Q: Is it legal to use AccountHarvester?</h3>
            <p>A: AccountHarvester should only be used with accounts you own or have explicit permission to check. Using it to attempt unauthorized access to accounts is illegal and against Steam's Terms of Service.</p>
            
            <h3>Q: How do I get a Steam API key?</h3>
            <p>A: You can obtain a Steam API key by visiting <a href="https://steamcommunity.com/dev/apikey">https://steamcommunity.com/dev/apikey</a>. You'll need a Steam account with at least one purchase to get an API key.</p>
            
            <h3>Q: What information can AccountHarvester retrieve?</h3>
            <p>A: AccountHarvester can verify account credentials, check if an account requires SteamGuard, retrieve the account's Steam ID, and list owned games (with a valid API key).</p>
            
            <h3>Q: What export formats are supported?</h3>
            <p>A: AccountHarvester supports exporting results in multiple formats including CSV, TXT, JSON, XML, and YAML. Each format has its own advantages - CSV is best for spreadsheets, JSON/XML/YAML for programmatic use, and TXT for readability.</p>
            
            <h3>Q: How do I customize the export filenames?</h3>
            <p>A: In the Export tab, you can enter a custom filename in the "Filename" field. You can also choose whether to add a timestamp to the filename using the "Add Timestamp" checkbox.</p>
            
            <h3>Q: What is the configuration backup feature?</h3>
            <p>A: The configuration backup feature allows you to save your current application settings (API keys, proxy settings, etc.) to a file. You can restore these settings later if needed, which is useful when moving to a new computer or recovering from a system issue.</p>
            
            <h3>Q: How do I backup my configuration?</h3>
            <p>A: Go to the Settings tab, then the "Backup & Restore" section. Click "Create Backup" to save your current settings. You can also restore from a previous backup or manage existing backups from this section.</p>
            
            <h3>Q: What does the cleanup utility do?</h3>
            <p>A: The cleanup utility helps maintain the application by removing temporary files. It can clear the API cache (to free memory and get fresh data), remove old log files, and delete temporary export files that are no longer needed.</p>
            
            <h3>Q: Why does AccountHarvester treat Error 50 as valid?</h3>
            <p>A: Error 50 (Service Unavailable) often indicates that the credentials are correct, but Steam is temporarily blocking the login attempt. This is a common response when checking multiple accounts, so it's treated as a valid account.</p>
            
            <h3>Q: How many accounts can I check at once?</h3>
            <p>A: There's no hard limit, but checking too many accounts in a short period may trigger rate limiting from Steam. Using proxies and adjusting the thread count can help manage larger batches.</p>
            
            <h3>Q: What proxy types are supported?</h3>
            <p>A: AccountHarvester supports HTTP and HTTPS proxies. Both anonymous proxies (ip:port) and authenticated proxies (ip:port:user:pass) are supported.</p>
            
            <h3>Q: Can AccountHarvester bypass SteamGuard?</h3>
            <p>A: No, AccountHarvester cannot bypass SteamGuard or two-factor authentication. It can only identify accounts that require these additional verification steps.</p>
            
            <h3>Q: Why are some valid accounts showing no games?</h3>
            <p>A: This could be due to several reasons: the account may have a private profile, it may not own any games, or there might be an issue with your API key.</p>
            
            <h3>Q: How can I improve the checking speed?</h3>
            <p>A: Increase the thread count in settings, use reliable proxies, and ensure your internet connection is stable. Also, regularly clearing the API cache can help maintain performance. Note that Steam rate limiting may still affect performance.</p>
            
            <h3>Q: Where are the results saved?</h3>
            <p>A: When exporting results, files are saved in the "exports" directory within the application folder. You can specify a custom filename when exporting.</p>
            
            <h3>Q: Can I run AccountHarvester from the command line?</h3>
            <p>A: Yes, AccountHarvester provides command-line interfaces for checking accounts, managing backups, and cleaning up temporary files. Use "python run.py --help" to see available commands.</p>
            
            <h3>Q: How do I clear the cache from command line?</h3>
            <p>A: Run "python run.py cleanup --cache" to clear the cache files. You can also use "--logs" to clear old logs or "--exports" to clear temporary exports.</p>
        """)
        faq_layout.addWidget(faq_text)
        
        help_tabs.addTab(faq_widget, "FAQ")
        
        # Keyboard Shortcuts tab
        shortcuts_widget = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_widget)
        
        shortcuts_text = QTextBrowser()
        shortcuts_text.setHtml("""
            <h1>Keyboard Shortcuts</h1>
            <p>The following keyboard shortcuts are available throughout the application:</p>
            
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr>
                    <th>Action</th>
                    <th>Shortcut (Windows)</th>
                    <th>Shortcut (Mac)</th>
                </tr>
                <tr>
                    <td>Check Account (Manual tab)</td>
                    <td>Ctrl+Enter</td>
                    <td>⌘+Enter</td>
                </tr>
                <tr>
                    <td>Browse for Account File</td>
                    <td>Ctrl+O</td>
                    <td>⌘+O</td>
                </tr>
                <tr>
                    <td>Start Checking Accounts</td>
                    <td>Ctrl+R</td>
                    <td>⌘+R</td>
                </tr>
                <tr>
                    <td>Stop Checking</td>
                    <td>Ctrl+S</td>
                    <td>⌘+S</td>
                </tr>
                <tr>
                    <td>Export Results</td>
                    <td>Ctrl+E</td>
                    <td>⌘+E</td>
                </tr>
                <tr>
                    <td>Switch to Manual Tab</td>
                    <td>Ctrl+1</td>
                    <td>⌘+1</td>
                </tr>
                <tr>
                    <td>Switch to Automatic Tab</td>
                    <td>Ctrl+2</td>
                    <td>⌘+2</td>
                </tr>
                <tr>
                    <td>Switch to Settings Tab</td>
                    <td>Ctrl+3</td>
                    <td>⌘+3</td>
                </tr>
                <tr>
                    <td>Switch to Help Tab</td>
                    <td>Ctrl+4</td>
                    <td>⌘+4</td>
                </tr>
                <tr>
                    <td>Save Settings</td>
                    <td>Ctrl+Shift+S</td>
                    <td>⌘+Shift+S</td>
                </tr>
                <tr>
                    <td>Quit Application</td>
                    <td>Alt+F4</td>
                    <td>⌘+Q</td>
                </tr>
            </table>
            
            <p><em>Note: Some shortcuts may vary depending on your operating system and keyboard layout.</em></p>
        """)
        shortcuts_layout.addWidget(shortcuts_text)
        
        help_tabs.addTab(shortcuts_widget, "Shortcuts")
        
        # Contact & Resources tab
        contact_widget = QWidget()
        contact_layout = QVBoxLayout(contact_widget)
        
        contact_text = QTextBrowser()
        contact_text.setOpenExternalLinks(True)
        contact_text.setHtml("""
            <h1>Contact & Resources</h1>
            
            <h2>Steam API Documentation</h2>
            <p>For information about the Steam API:</p>
            <ul>
                <li><a href="https://developer.valvesoftware.com/wiki/Steam_Web_API">Steam Web API Documentation</a></li>
                <li><a href="https://steamcommunity.com/dev">Steam API Key Registration</a></li>
                <li><a href="https://partner.steamgames.com/doc/webapi">Steam Partner Web API Documentation</a></li>
            </ul>
            
            <h2>Steam Libraries</h2>
            <ul>
                <li><a href="https://github.com/ValvePython/steam">ValvePython/steam</a> - Python library for interacting with Steam</li>
                <li><a href="https://github.com/SteamDatabase/SteamKit">SteamKit</a> - .NET library for interacting with Steam</li>
            </ul>
            
            <h2>Support</h2>
            <p>For questions and support:</p>
            <ul>
                <li>Check the documentation in this help section</li>
                <li>Consult the README file included with the application</li>
            </ul>
            
            <h2>Legal Notice</h2>
            <p>This application is for educational purposes only. The developer is not responsible for any misuse of this application.</p>
            <p>Always respect Steam's <a href="https://store.steampowered.com/subscriber_agreement/">Subscriber Agreement</a> and <a href="https://store.steampowered.com/eula/">Terms of Service</a>.</p>
        """)
        contact_layout.addWidget(contact_text)
        
        help_tabs.addTab(contact_widget, "Resources")
        
        # Add buttons at the bottom
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)
        
        # Clear cache button
        clear_cache_button = QPushButton("Clear API Cache")
        clear_cache_button.setToolTip("Clear the cached API responses to fetch fresh data")
        clear_cache_button.clicked.connect(self.clear_api_cache)
        buttons_layout.addWidget(clear_cache_button)
        
        # Open logs button
        open_logs_button = QPushButton("Open Log File")
        open_logs_button.setToolTip("Open the application log file")
        open_logs_button.clicked.connect(self.open_log_file)
        buttons_layout.addWidget(open_logs_button)
        
        # Add spacer
        buttons_layout.addStretch()
        
        # Visit Steam button
        visit_steam_button = QPushButton("Visit Steam")
        visit_steam_button.setToolTip("Open the Steam website")
        visit_steam_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://steamcommunity.com/")))
        buttons_layout.addWidget(visit_steam_button)
    
    def clear_api_cache(self):
        """Clear the Steam API cache"""
        from core.steam_api import steam_api
        try:
            steam_api.clear_cache()
            # Show a message in the parent widget, if possible
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage("API cache cleared successfully")
        except Exception as e:
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage(f"Error clearing cache: {e}")
    
    def open_log_file(self):
        """Open the application log file"""
        from utils.logger import logger
        log_file = logger.get_log_file_path()
        if log_file and os.path.exists(log_file):
            QDesktopServices.openUrl(QUrl.fromLocalFile(log_file))
        elif hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage("Log file not found")
