"""
Cryptography utilities for secure data storage
"""
import os
import base64
import getpass
import hashlib
import platform
import secrets
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from utils.logger import logger

# File to store salt for key derivation
SALT_FILE = Path("config/.salt")

def get_machine_id():
    """Get a unique identifier for the machine to use in key derivation"""
    system = platform.system()
    try:
        if system == "Windows":
            import winreg
            registry = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
            key = winreg.OpenKey(registry, r"SOFTWARE\Microsoft\Cryptography")
            machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
            return machine_guid
        elif system == "Darwin":  # macOS
            # Use IOPlatformUUID which is relatively stable on macOS
            from subprocess import check_output
            return check_output(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice']).decode('utf-8').split('IOPlatformUUID')[1].split('"')[2]
        else:  # Linux and other Unix-like
            # Use machine-id which is stable on modern Linux systems
            try:
                with open('/etc/machine-id', 'r') as f:
                    return f.read().strip()
            except FileNotFoundError:
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    return f.read().strip()
    except Exception as e:
        logger.warning(f"Could not get machine ID, using fallback: {str(e)}")
        # Use hostname as fallback
        return platform.node()

def get_salt():
    """Get the salt for key derivation, creating it if it doesn't exist"""
    if SALT_FILE.exists():
        with open(SALT_FILE, 'rb') as f:
            return f.read()
    else:
        # Generate a new salt
        salt = os.urandom(16)
        os.makedirs(SALT_FILE.parent, exist_ok=True)
        with open(SALT_FILE, 'wb') as f:
            f.write(salt)
        return salt

def get_encryption_key():
    """Generate an encryption key based on machine-specific information"""
    # Get machine-specific identifiers
    machine_id = get_machine_id()
    username = getpass.getuser()
    
    # Combine with salt for key derivation
    salt = get_salt()
    
    # Create a key using PBKDF2
    password = f"{machine_id}:{username}".encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    return key

def encrypt(data):
    """Encrypt data using Fernet symmetric encryption"""
    if not data:
        return ""
    
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        return fernet.encrypt(data.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption error: {str(e)}", exc_info=True)
        # Return a special marker to indicate encryption failure
        return f"ENCRYPTION_FAILED_{secrets.token_hex(8)}"

def decrypt(encrypted_data):
    """Decrypt data that was encrypted using the encrypt function"""
    if not encrypted_data:
        return ""
    
    # Check if this is a marker for encryption failure
    if encrypted_data.startswith("ENCRYPTION_FAILED_"):
        logger.warning("Attempting to decrypt data that had encryption failure")
        return ""
    
    try:
        key = get_encryption_key()
        fernet = Fernet(key)
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption error: {str(e)}", exc_info=True)
        return "" 