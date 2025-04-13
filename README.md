# AccountHarvester

A Python application to validate Steam accounts and check for owned games.

## Features

- Check Steam accounts using the format `username:password`
- Handle SteamGuard authentication and Error Code 50 properly
- Verify if accounts own paid games
- Export results to multiple formats: CSV, JSON, TXT, XML, and YAML
- Support multi-threaded operations for efficiency
- Proxy support with dynamic rotation
- Advanced rate limiting to prevent 429 errors

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/doshibadev/AccountHarvester.git
   cd AccountHarvester
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv .venv
   ```
   
3. Activate the virtual environment:
   - Windows: `.venv\Scripts\activate`
   - Linux/Mac: `source .venv/bin/activate`

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

### Command Line Interface

The application can be used from the command line with various options:

#### Check a single account:
```
python app.py check "username:password"
```

#### Check accounts from a file:
```
python app.py file accounts.txt --export
```

#### Export to specific formats:
```
# Export to CSV (default)
python app.py file accounts.txt --export --export-format csv

# Export to JSON
python app.py file accounts.txt --export --export-format json

# Export to plain text
python app.py file accounts.txt --export --export-format txt

# Export to XML
python app.py file accounts.txt --export --export-format xml

# Export to YAML
python app.py file accounts.txt --export --export-format yml
```

#### Manage proxies:
```
# Add a proxy
python app.py proxy --add "ip:port"

# Load proxies from a file
python app.py proxy --file proxies.txt

# Test loaded proxies
python app.py proxy --test

# Enable proxy usage
python app.py proxy --enable

# Disable proxy usage
python app.py proxy --disable
```

#### Set Steam API key (required for game checking):
```
python app.py --api-key "YOUR_STEAM_API_KEY"
```

#### Set thread count for multiple account checking:
```
python app.py --threads 10 file accounts.txt
```

#### Configure rate limiting:
```
# Enable or disable rate limiting
python app.py --rate-limit-enabled true

# Set default rate (requests per second)
python app.py --default-rate 1.0

# Set rate for specific Steam API services
python app.py --player-service-rate 0.5
python app.py --user-service-rate 0.5
python app.py --store-api-rate 0.25

# Enable or disable adaptive rate limiting
python app.py --adaptive-rate-limiting true
```

### Graphical User Interface (Coming Soon)

The GUI version of the application is featuring:

- **Manual Tab**: Single account credential checking with detailed results
- **Automatic Tab**: Bulk account checking from file with threading support and export functionality
- **Settings Tab**: Configure API keys, thread count, proxy settings, and rate limiting
- **Help Tab**: Documentation and guidance

## Export Formats

AccountHarvester supports multiple export formats to suit your needs:

1. **CSV** (default) - Comma-separated values format, ideal for spreadsheet applications
2. **JSON** - JavaScript Object Notation, useful for web applications and data processing
3. **TXT** - Plain text format with human-readable account details
4. **XML** - Extensible Markup Language, structured data for various applications
5. **YAML** - YAML Ain't Markup Language, a human-friendly data serialization format

All exports include:
- Account credentials
- Account status
- Steam ID (if available)
- Error messages (if any)
- Games owned (name and appid, if available)

## Account Status Types

1. **Valid** - Successfully logged in OR returned Error Code 50 (valid credentials but too many people logged in)
2. **Error** - Any error code except 50
3. **SteamGuard** - Account has 2FA or SteamGuard activated

## File Formats

### Accounts File
One account per line in the format:
```
username1:password1
username2:password2
```

### Proxy File
One proxy per line in the format:
```
ip:port
ip:port:username:password
```

## Steam API Key

To check owned games, you need a Steam API key from [Steam Web API](https://steamcommunity.com/dev/apikey).

## Rate Limiting

The application includes an advanced rate limiting system to prevent 429 (Too Many Requests) errors from the Steam API. Key features include:

- **Token Bucket Algorithm**: Smooth request distribution over time
- **Per-Service Limits**: Different limits for different API services
- **Adaptive Rate Limiting**: Automatically adjusts rates based on server responses
- **Configurable Settings**: Fine-tune rate limits via GUI or command line
- **Proxy Integration**: Works with proxy rotation to maximize throughput

Default rate limits:
- Default API: 1.0 requests/second
- Player Service: 0.5 requests/second
- User Service: 0.5 requests/second
- Store API: 0.25 requests/second

These limits can be adjusted based on your specific needs and API usage patterns.

## License

This project is for educational purposes only. Use at your own risk and responsibility.

## Disclaimer

This software is provided for educational purposes only. Check Steam's Terms of Service before use.
