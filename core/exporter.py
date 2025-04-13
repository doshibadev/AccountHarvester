import csv
import os
import json
import xml.dom.minidom
import yaml
from pathlib import Path
from datetime import datetime
from utils.logger import logger
from core.account import AccountStatus

class Exporter:
    """Handles exporting account results to various formats"""
    
    def __init__(self, export_dir="exports"):
        self.export_dir = Path(export_dir)
        # Create exports directory if it doesn't exist
        self.export_dir.mkdir(exist_ok=True)
    
    def _generate_filename(self, prefix, extension):
        """Generate a unique filename with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{prefix}_{timestamp}.{extension}"
    
    def export_to_csv(self, accounts, filename=None, include_games=True, options=None):
        """Export accounts to CSV file"""
        if not accounts:
            logger.warning("No accounts to export")
            return None
            
        if not filename:
            filename = self._generate_filename("accounts", "csv")
            
        file_path = self.export_dir / filename
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Determine fields based on first account to check available attributes
                sample_account = accounts[0] if accounts else None
                header = []
                
                # Include fields based on options or defaults
                if options is None:
                    options = {}
                    
                include_username = options.get('include_username', True)
                include_password = options.get('include_passwords', True)
                include_status = options.get('include_status', True)
                include_steam_id = options.get('include_steam_ids', True)
                include_error = True  # Always include error messages
                include_email = options.get('include_email', True)
                include_games_count = options.get('include_games', True)
                include_games_list = options.get('include_games_list', False)
                
                # Standard fields
                if include_username:
                    header.append('Username')
                if include_password:
                    header.append('Password')
                if include_status and hasattr(sample_account, 'status'):
                    header.append('Status')
                if include_steam_id and hasattr(sample_account, 'steam_id'):
                    header.append('Steam ID')
                if include_email and hasattr(sample_account, 'email'):
                    header.append('Email')
                if include_error and hasattr(sample_account, 'error_message'):
                    header.append('Error Message')
                if include_games_count and hasattr(sample_account, 'games'):
                    header.append('Games Count')
                if include_games_list and hasattr(sample_account, 'games'):
                    header.append('Game List')
                
                # Create CSV writer and write header
                writer = csv.writer(csvfile)
                writer.writerow(header)
                
                # Write account data
                for account in accounts:
                    row = []
                    
                    if include_username:
                        row.append(account.username)
                    if include_password:
                        row.append(account.password)
                    if include_status and hasattr(account, 'status'):
                        row.append(account.status.value if hasattr(account.status, 'value') else str(account.status))
                    if include_steam_id and hasattr(account, 'steam_id'):
                        row.append(account.steam_id if account.steam_id else '')
                    if include_email and hasattr(account, 'email'):
                        row.append(account.email if account.email else '')
                    if include_error and hasattr(account, 'error_message'):
                        row.append(account.error_message if account.error_message else '')
                    if include_games_count and hasattr(account, 'games'):
                        row.append(str(len(account.games)) if account.games else '0')
                    if include_games_list and hasattr(account, 'games') and account.games:
                        # Create a comma-separated list of game names
                        game_names = [game.get('name', f"Game {game.get('appid', 'Unknown')}") for game in account.games]
                        row.append('; '.join(game_names))
                    elif include_games_list:
                        row.append('')
                        
                    writer.writerow(row)
            
            logger.info(f"Exported {len(accounts)} accounts to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return None
    
    def export_by_status(self, account_results, format="csv"):
        """Export accounts grouped by status"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        result_files = {}
        
        try:
            # Export each status group to a separate file
            for status, accounts in account_results.items():
                if accounts:
                    filename = f"{status.value.lower()}_{timestamp}.{format}"
                    file_path = self.export_accounts(accounts, filename, format)
                    if file_path:
                        result_files[status.value] = str(file_path)
            
            return result_files
            
        except Exception as e:
            logger.error(f"Error exporting by status: {e}")
            return {}
    
    def export_to_json(self, accounts, filename=None):
        """Export accounts to JSON file"""
        if not accounts:
            logger.warning("No accounts to export")
            return None
            
        if not filename:
            filename = self._generate_filename("accounts", "json")
            
        file_path = self.export_dir / filename
        
        try:
            # Convert accounts to dictionaries
            account_dicts = [
                account.to_dict() if hasattr(account, 'to_dict') else {
                    'username': account.username,
                    'password': account.password,
                    'status': account.status.value if hasattr(account, 'status') else "Unknown",
                    'error': account.error_message if hasattr(account, 'error_message') else None,
                    'steam_id': account.steam_id if hasattr(account, 'steam_id') else None,
                    'games': account.games if hasattr(account, 'games') else []
                }
                for account in accounts
            ]
            
            with open(file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(account_dicts, jsonfile, indent=4)
            
            logger.info(f"Exported {len(accounts)} accounts to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            return None
    
    def export_to_txt(self, accounts, filename=None, include_games=True, options=None):
        """Export accounts to a plain text file"""
        if not accounts:
            logger.warning("No accounts to export")
            return None
            
        if not filename:
            filename = self._generate_filename("accounts", "txt")
            
        file_path = self.export_dir / filename
        
        try:
            # Process options
            if options is None:
                options = {}
                
            include_username = options.get('include_username', True)
            include_password = options.get('include_passwords', True)
            include_status = options.get('include_status', True)
            include_steam_id = options.get('include_steam_ids', True)
            include_error = True  # Always include error messages
            include_email = options.get('include_email', True)
            include_games_count = options.get('include_games', True)
            include_games_list = options.get('include_games_list', False)
            
            with open(file_path, 'w', encoding='utf-8') as txtfile:
                txtfile.write("=== Account Harvester Export ===\n")
                txtfile.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                txtfile.write(f"Total Accounts: {len(accounts)}\n\n")
                
                for i, account in enumerate(accounts, 1):
                    txtfile.write(f"--- Account {i} ---\n")
                    
                    if include_username:
                        txtfile.write(f"Username: {account.username}\n")
                    
                    if include_password:
                        txtfile.write(f"Password: {account.password}\n")
                    
                    if include_status and hasattr(account, 'status'):
                        txtfile.write(f"Status: {account.status.value}\n")
                    
                    if include_steam_id and hasattr(account, 'steam_id') and account.steam_id:
                        txtfile.write(f"Steam ID: {account.steam_id}\n")
                    
                    if include_email and hasattr(account, 'email') and account.email:
                        txtfile.write(f"Email: {account.email}\n")
                    
                    if include_error and hasattr(account, 'error_message') and account.error_message:
                        txtfile.write(f"Error: {account.error_message}\n")
                    
                    if include_games_count and hasattr(account, 'games'):
                        txtfile.write(f"Games Count: {len(account.games) if account.games else 0}\n")
                    
                    if include_games_list and hasattr(account, 'games') and account.games:
                        txtfile.write("Games List:\n")
                        for game in account.games:
                            game_name = game.get('name', f"Unknown Game {game.get('appid', '')}")
                            txtfile.write(f"  - {game_name}\n")
                    
                    txtfile.write("\n")
            
            logger.info(f"Exported {len(accounts)} accounts to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error exporting to TXT: {e}")
            return None
    
    def export_to_xml(self, accounts, filename=None, include_games=True, options=None):
        """Export accounts to an XML file"""
        if not accounts:
            logger.warning("No accounts to export")
            return None
            
        if not filename:
            filename = self._generate_filename("accounts", "xml")
            
        file_path = self.export_dir / filename
        
        try:
            # Process options
            if options is None:
                options = {}
                
            include_username = options.get('include_username', True)
            include_password = options.get('include_passwords', True)
            include_status = options.get('include_status', True)
            include_steam_id = options.get('include_steam_ids', True)
            include_error = True  # Always include error messages
            include_email = options.get('include_email', True)
            include_games_count = options.get('include_games', True)
            include_games_list = options.get('include_games_list', False)
            
            # Create XML document
            doc = xml.dom.minidom.getDOMImplementation().createDocument(None, "accounts", None)
            root = doc.documentElement
            
            # Add metadata
            metadata = doc.createElement("metadata")
            metadata.setAttribute("export_date", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            metadata.setAttribute("total_accounts", str(len(accounts)))
            root.appendChild(metadata)
            
            # Add each account
            for account in accounts:
                account_elem = doc.createElement("account")
                
                if include_username:
                    username_elem = doc.createElement("username")
                    username_elem.appendChild(doc.createTextNode(account.username))
                    account_elem.appendChild(username_elem)
                
                if include_password:
                    password_elem = doc.createElement("password")
                    password_elem.appendChild(doc.createTextNode(account.password))
                    account_elem.appendChild(password_elem)
                
                if include_status and hasattr(account, 'status'):
                    status_elem = doc.createElement("status")
                    status_elem.appendChild(doc.createTextNode(account.status.value))
                    account_elem.appendChild(status_elem)
                
                if include_steam_id and hasattr(account, 'steam_id') and account.steam_id:
                    steamid_elem = doc.createElement("steam_id")
                    steamid_elem.appendChild(doc.createTextNode(str(account.steam_id)))
                    account_elem.appendChild(steamid_elem)
                
                if include_email and hasattr(account, 'email') and account.email:
                    email_elem = doc.createElement("email")
                    email_elem.appendChild(doc.createTextNode(account.email))
                    account_elem.appendChild(email_elem)
                
                if include_error and hasattr(account, 'error_message') and account.error_message:
                    error_elem = doc.createElement("error_message")
                    error_elem.appendChild(doc.createTextNode(account.error_message))
                    account_elem.appendChild(error_elem)
                
                if include_games_count and hasattr(account, 'games'):
                    games_count_elem = doc.createElement("games_count")
                    games_count = str(len(account.games) if account.games else 0)
                    games_count_elem.appendChild(doc.createTextNode(games_count))
                    account_elem.appendChild(games_count_elem)
                
                if include_games_list and hasattr(account, 'games') and account.games:
                    games_elem = doc.createElement("games")
                    
                    for game in account.games:
                        game_elem = doc.createElement("game")
                        
                        name_elem = doc.createElement("name")
                        name_elem.appendChild(doc.createTextNode(game.get('name', 'Unknown Game')))
                        game_elem.appendChild(name_elem)
                        
                        if 'appid' in game:
                            appid_elem = doc.createElement("appid")
                            appid_elem.appendChild(doc.createTextNode(str(game['appid'])))
                            game_elem.appendChild(appid_elem)
                        
                        if 'playtime_forever' in game:
                            playtime_elem = doc.createElement("playtime")
                            playtime_elem.appendChild(doc.createTextNode(str(game['playtime_forever'])))
                            game_elem.appendChild(playtime_elem)
                        
                        games_elem.appendChild(game_elem)
                    
                    account_elem.appendChild(games_elem)
                
                root.appendChild(account_elem)
            
            # Write to file with pretty formatting
            with open(file_path, 'w', encoding='utf-8') as xmlfile:
                xmlfile.write(doc.toprettyxml(indent="  "))
            
            logger.info(f"Exported {len(accounts)} accounts to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error exporting to XML: {e}")
            return None
    
    def export_to_yml(self, accounts, filename=None, include_games=True, options=None):
        """Export accounts to a YAML file"""
        if not accounts:
            logger.warning("No accounts to export")
            return None
            
        if not filename:
            filename = self._generate_filename("accounts", "yml")
            
        file_path = self.export_dir / filename
        
        try:
            # Process options
            if options is None:
                options = {}
                
            include_username = options.get('include_username', True)
            include_password = options.get('include_passwords', True)
            include_status = options.get('include_status', True)
            include_steam_id = options.get('include_steam_ids', True)
            include_error = True  # Always include error messages
            include_email = options.get('include_email', True)
            include_games_count = options.get('include_games', True)
            include_games_list = options.get('include_games_list', False)
            
            # Build YAML data structure
            yaml_data = {
                'metadata': {
                    'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_accounts': len(accounts)
                },
                'accounts': []
            }
            
            for account in accounts:
                account_data = {}
                
                if include_username:
                    account_data['username'] = account.username
                
                if include_password:
                    account_data['password'] = account.password
                
                if include_status and hasattr(account, 'status'):
                    account_data['status'] = account.status.value
                
                if include_steam_id and hasattr(account, 'steam_id') and account.steam_id:
                    account_data['steam_id'] = account.steam_id
                
                if include_email and hasattr(account, 'email') and account.email:
                    account_data['email'] = account.email
                
                if include_error and hasattr(account, 'error_message') and account.error_message:
                    account_data['error'] = account.error_message
                
                if include_games_count and hasattr(account, 'games'):
                    account_data['games_count'] = len(account.games) if account.games else 0
                
                if include_games_list and hasattr(account, 'games') and account.games:
                    account_data['games'] = []
                    for game in account.games:
                        game_data = {
                            'name': game.get('name', 'Unknown Game'),
                            'appid': game.get('appid', 'unknown')
                        }
                        if 'playtime_forever' in game:
                            game_data['playtime'] = game['playtime_forever']
                        account_data['games'].append(game_data)
                
                yaml_data['accounts'].append(account_data)
            
            # Write YAML file
            with open(file_path, 'w', encoding='utf-8') as ymlfile:
                yaml.dump(yaml_data, ymlfile, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Exported {len(accounts)} accounts to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error exporting to YAML: {e}")
            return None
    
    def export_accounts(self, accounts, filename=None, options=None):
        """
        Export accounts to the specified format
        
        Args:
            accounts: List of account objects to export
            filename: Target filename (will be generated if None)
            options: Dictionary with export options:
                - format: Export format (csv, json, txt, xml, yml)
                - include_passwords: Whether to include passwords in export
                - include_steam_ids: Whether to include Steam IDs
                - include_games: Whether to include game information
                - include_games_list: Whether to include detailed games list
                - include_email: Whether to include email addresses
                - include_status: Whether to include account status
                - include_username: Whether to include usernames
                - only_valid: Export only valid accounts
                
        Returns:
            (success, message) tuple where success is a boolean and message is count or error
        """
        if not accounts:
            logger.warning("No accounts to export")
            return False, "No accounts to export"
        
        # Use default options if none provided
        if options is None:
            options = {
                'format': 'csv',
                'include_passwords': True,
                'include_steam_ids': True,
                'include_games': True,
                'include_games_list': False,
                'include_email': True,
                'include_status': True,
                'include_username': True,
                'only_valid': False
            }
        
        # Apply filters
        filtered_accounts = accounts
        
        # Filter by valid accounts if requested
        if options.get('only_valid', False):
            filtered_accounts = [
                account for account in accounts 
                if hasattr(account, 'status') and account.status == AccountStatus.VALID
            ]
            
            if not filtered_accounts:
                logger.warning("No valid accounts to export")
                return False, "No valid accounts to export"
        
        # Filter by accounts with games if requested
        if options.get('only_with_games', False):
            filtered_accounts = [
                account for account in filtered_accounts 
                if hasattr(account, 'games') and account.games
            ]
            
            if not filtered_accounts:
                logger.warning("No accounts with games to export")
                return False, "No accounts with games to export"
        
        # Generate filename if not provided
        if not filename:
            ext = options.get('format', 'csv').lower()
            filename = self._generate_filename("accounts", ext)
        
        try:
            # Choose the appropriate export function based on format
            export_format = options.get('format', 'csv').lower()
            
            if export_format == 'csv':
                path = self.export_to_csv(
                    filtered_accounts, 
                    filename, 
                    include_games=options.get('include_games', True),
                    options=options
                )
            elif export_format == 'json':
                path = self.export_to_json(filtered_accounts, filename)
            elif export_format == 'txt':
                path = self.export_to_txt(
                    filtered_accounts, 
                    filename, 
                    include_games=options.get('include_games', True),
                    options=options
                )
            elif export_format == 'xml':
                path = self.export_to_xml(
                    filtered_accounts, 
                    filename, 
                    include_games=options.get('include_games', True),
                    options=options
                )
            elif export_format == 'yml' or export_format == 'yaml':
                path = self.export_to_yml(
                    filtered_accounts, 
                    filename, 
                    include_games=options.get('include_games', True),
                    options=options
                )
            else:
                # Default to CSV if format is unknown
                logger.warning(f"Unknown export format: {export_format}. Using CSV.")
                path = self.export_to_csv(filtered_accounts, filename, include_games=True, options=options)
                
            if path:
                # If path is a Path object, convert to string
                path_str = str(path) if hasattr(path, '__str__') else path
                return True, len(filtered_accounts)
            else:
                return False, "Export failed"
                
        except Exception as e:
            logger.error(f"Error exporting accounts: {e}", exc_info=True)
            return False, str(e)
    
    def combine_all_valid(self, account_results, format="csv"):
        """Combine all valid accounts (including error 50) into a single file"""
        valid_accounts = account_results.get(AccountStatus.VALID, [])
        
        if not valid_accounts:
            logger.warning("No valid accounts to export")
            return None
            
        filename = self._generate_filename("valid_accounts", format)
        return self.export_accounts(valid_accounts, filename, format, include_games=True)

# Global exporter instance
exporter = Exporter()
