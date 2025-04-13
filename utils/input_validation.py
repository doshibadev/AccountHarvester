"""
Input validation utilities to prevent security issues
"""
import re
import os
import json
from pathlib import Path
from utils.logger import logger
from typing import Any, Dict, List, Optional, Tuple, Union


def validate_api_key(key: str) -> Tuple[bool, str]:
    """
    Validate Steam API key format
    
    Args:
        key: The API key to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key or not isinstance(key, str):
        return False, "API key cannot be empty"
    
    # Steam API keys are 32 character hex values
    if not re.match(r'^[A-Z0-9]{32}$', key):
        return False, "API key must be 32 characters long and contain only uppercase letters and numbers"
    
    return True, ""


def validate_credentials(credentials: str) -> Tuple[bool, str, Optional[Tuple[str, str]]]:
    """
    Validate account credentials format
    
    Args:
        credentials: The credentials string in format username:password
        
    Returns:
        Tuple of (is_valid, error_message, credentials_tuple or None)
    """
    if not credentials or not isinstance(credentials, str):
        return False, "Credentials cannot be empty", None
    
    parts = credentials.split(':', 1)
    if len(parts) != 2:
        return False, "Credentials must be in the format 'username:password'", None
    
    username, password = parts
    
    if not username:
        return False, "Username cannot be empty", None
    
    if not password:
        return False, "Password cannot be empty", None
    
    # Basic XSS prevention
    if re.search(r'[<>]', username) or re.search(r'[<>]', password):
        return False, "Invalid characters in credentials", None
    
    return True, "", (username, password)


def validate_file_path(file_path: str, must_exist: bool = True, 
                      allowed_extensions: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Validate a file path
    
    Args:
        file_path: The file path to validate
        must_exist: Whether the file must exist
        allowed_extensions: List of allowed file extensions
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path or not isinstance(file_path, str):
        return False, "File path cannot be empty"
    
    # Path traversal prevention
    path = Path(file_path)
    try:
        # Get the absolute normalized path
        abs_path = os.path.normpath(os.path.abspath(path))
        
        # Check for path traversal attempts
        if ".." in path.parts:
            return False, "Path traversal detected"
        
        # Check if file exists if required
        if must_exist and not os.path.exists(abs_path):
            return False, f"File does not exist: {file_path}"
        
        # Check file extension if specified
        if allowed_extensions:
            file_ext = os.path.splitext(file_path)[1].lower()
            if not file_ext or file_ext.lstrip('.') not in [ext.lstrip('.') for ext in allowed_extensions]:
                return False, f"Invalid file extension. Allowed: {', '.join(allowed_extensions)}"
    
    except (ValueError, TypeError) as e:
        logger.error(f"File path validation error: {str(e)}", exc_info=True)
        return False, f"Invalid file path: {str(e)}"
    
    return True, ""


def validate_proxy(proxy: str) -> Tuple[bool, str]:
    """
    Validate proxy format
    
    Args:
        proxy: The proxy string to validate (ip:port or ip:port:user:pass)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not proxy or not isinstance(proxy, str):
        return False, "Proxy cannot be empty"
    
    parts = proxy.split(':')
    
    # Check for ip:port or ip:port:user:pass format
    if len(parts) not in (2, 4):
        return False, "Proxy must be in format 'ip:port' or 'ip:port:user:pass'"
    
    ip, port = parts[0], parts[1]
    
    # Validate IP address
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(ip_pattern, ip):
        return False, "Invalid IP address format"
    
    # Validate port number
    try:
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            return False, "Port must be between 1 and 65535"
    except ValueError:
        return False, "Port must be a number"
    
    return True, ""


def validate_thread_count(count: Any) -> Tuple[bool, str, int]:
    """
    Validate thread count
    
    Args:
        count: The thread count to validate
        
    Returns:
        Tuple of (is_valid, error_message, validated_count)
    """
    try:
        # Convert to int if string
        if isinstance(count, str):
            count = int(count)
        elif not isinstance(count, int):
            return False, "Thread count must be a number", 1
        
        # Validate range
        if count < 1:
            return False, "Thread count must be at least 1", 1
        
        if count > 10:
            return False, "Thread count cannot exceed 10 for security reasons", 10
            
        return True, "", count
    except ValueError:
        return False, "Invalid thread count", 1


def sanitize_input(input_str: str) -> str:
    """
    Sanitize user input to prevent injection attacks
    
    Args:
        input_str: The input string to sanitize
        
    Returns:
        Sanitized string
    """
    if not input_str or not isinstance(input_str, str):
        return ""
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\'&;()]', '', input_str)
    
    # Limit length
    return sanitized[:1000]  # Reasonable limit for text inputs


def safe_load_json(json_str: str) -> Tuple[bool, str, Any]:
    """
    Safely load JSON string
    
    Args:
        json_str: JSON string to load
        
    Returns:
        Tuple of (success, error_message, parsed_data)
    """
    try:
        data = json.loads(json_str)
        return True, "", data
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {str(e)}", exc_info=True)
        return False, f"Invalid JSON format: {str(e)}", None
    except Exception as e:
        logger.error(f"Unexpected error parsing JSON: {str(e)}", exc_info=True)
        return False, f"Error processing JSON: {str(e)}", None 