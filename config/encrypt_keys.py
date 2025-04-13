#!/usr/bin/env python3
"""
Migration script to encrypt API keys in settings file
Run this once to encrypt any existing unencrypted API keys
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from utils.logger import setup_logging, logger
from utils.crypto import encrypt

def migrate_settings_file():
    """Migrate settings file to use encrypted API keys"""
    settings_file = Path("config/app_settings.json")
    
    if not settings_file.exists():
        logger.info("No settings file found, nothing to migrate")
        print("No settings file found, nothing to migrate")
        return False
    
    try:
        # Read existing settings
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        # Check if API key exists and is not already encrypted
        if 'api_key' in settings and settings['api_key']:
            api_key = settings['api_key']
            
            # Only encrypt if it doesn't look like it's already encrypted
            # Fernet-encrypted strings start with 'gAAAAA'
            if not api_key.startswith('gAAAAA'):
                logger.info("Encrypting API key in settings file")
                print("Encrypting API key in settings file...")
                
                # Encrypt the API key
                encrypted_key = encrypt(api_key)
                settings['api_key'] = encrypted_key
                
                # Save the updated settings
                with open(settings_file, 'w') as f:
                    json.dump(settings, f, indent=4)
                
                logger.info("API key successfully encrypted")
                print("API key successfully encrypted")
                return True
            else:
                logger.info("API key is already encrypted")
                print("API key is already encrypted, no action needed")
                return False
        else:
            logger.info("No API key found in settings file")
            print("No API key found in settings file, nothing to encrypt")
            return False
    except Exception as e:
        logger.error(f"Error migrating settings file: {str(e)}", exc_info=True)
        print(f"Error migrating settings file: {str(e)}")
        return False

if __name__ == "__main__":
    # Set up logging
    setup_logging()
    migrate_settings_file() 