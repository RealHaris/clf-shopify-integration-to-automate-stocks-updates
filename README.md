# CLF Stock Update Automation

This project automates the synchronization of stock levels between CLF Distribution and Shopify platforms.

## Project Structure

```
UpdateStocks/
├── api/
│   ├── __init__.py
│   ├── clf_api.py        # CLF Distribution API client
│   └── shopify_api.py    # Shopify API client
├── utils/
│   ├── __init__.py
│   ├── logger_config.py  # Logging configuration
│   ├── email_utils.py    # Email sending utility using SendGrid
│   └── file_utils.py     # File handling utilities
├── logs/                 # Directory for log files
├── main.py              # Main execution script
├── requirements.txt     # Project dependencies
└── README.md           # Project documentation
```

## Installation

To set up the project, clone the repository and install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. **Update Credentials**: 
   - Update the `credentials.json` file in the `data` directory with your CLF and Shopify credentials, as well as your SendGrid API key and email addresses.

2. **Run the Main Script**:
   - Execute the main script to start the stock update process:
   ```bash
   python main.py
   ```

## Functionalities

### 1. Automated Stock Level Synchronization
- The script retrieves stock levels from CLF Distribution and updates the corresponding inventory levels in Shopify.

### 2. Email Notifications
- The script sends email notifications using SendGrid in the following scenarios:
  - **Completion Notification**: When the stock update process completes successfully, including a summary of products updated and attached logs.
  - **Token Generation Limit Exceeded**: When the token generation limit is exceeded, notifying that the script has stopped due to token generation limits.

### 3. Logging
- Logs are stored in the `logs` directory. The script generates logs for both successful operations and errors, which can be useful for debugging and monitoring.

### 4. Error Handling
- The system includes comprehensive error handling for:
  - Network errors
  - API authentication failures
  - Rate limiting
  - Data parsing errors
  - Product not found scenarios

### 5. Rate Limit Handling
- The script implements rate limit handling for the Shopify API to ensure compliance with API usage limits.

### 6. Automatic Token Refresh
- The script automatically refreshes the authentication token for the CLF API when it expires.

### 7. Detailed Logging
- The script generates detailed logs with separate files for different types of logs (general, crash, and update logs).

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Credentials**:
   - CLF Distribution credentials are currently in `clf_api.py`.
   - Shopify credentials are in `shopify_api.py`.
   - Note: In production, these should be moved to environment variables.

3. **Ensure the Logs Directory Exists**:
   - The `logs` directory will be created automatically if not present.

## Future Improvements

1. Move credentials to environment variables.
2. Add a configuration file for API endpoints and other settings.
3. Implement more robust rate limit handling.
4. Add automated testing.
5. Add monitoring and alerting capabilities.

## License

This project is licensed under the MIT License.
