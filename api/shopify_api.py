import requests
import json
import time
from datetime import datetime
import os
from utils.logger_config import setup_logger

general_logger = setup_logger('general_logger')
crash_logger = setup_logger('crash_logger')
update_logger = setup_logger('update_logger')

class ShopifyAPI:
    def __init__(self, access_token=None, shop_url=None, location_id=None):
        """Initialize ShopifyAPI with credentials"""
        try:
            # Load credentials from JSON file
            credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'credentials.json')
            with open(credentials_path, 'r') as f:
                credentials = json.load(f)['shopify']
            
            self.access_token = access_token or credentials['access_token']
            self.shop_url = shop_url or credentials['shop_url']
            self.location_id = location_id or credentials['location_id']
            self.headers = {
                'X-Shopify-Access-Token': self.access_token,
                'Content-Type': 'application/json'
            }
            self.api_version = '2023-04'
            
            # Rate limiting parameters
            self.max_retries = 5
            self.initial_retry_delay = 1
            self.max_retry_delay = 16
            self.rate_limit_threshold = 0.8
            
            # Track API usage
            self.current_api_usage = 0
            self.max_api_limit = 40  # Default Shopify API limit per second
            self.last_reset_time = time.time()
            self.default_delay = 0.5
            
            general_logger.info("ShopifyAPI initialized successfully")
            
        except FileNotFoundError:
            crash_logger.error("Credentials file not found at: " + credentials_path)
            raise
        except json.JSONDecodeError:
            crash_logger.error("Invalid JSON in credentials file")
            raise
        except KeyError as e:
            crash_logger.error(f"Missing required credential: {str(e)}")
            raise
        except Exception as e:
            crash_logger.error(f"Unexpected error during initialization: {str(e)}")
            raise

    def _reset_api_usage(self):
        """Reset API usage counter and update last reset time"""
        self.current_api_usage = 0
        self.last_reset_time = time.time()
        self.default_delay = 0.5
        general_logger.info("API usage counter reset")

    def _handle_rate_limits(self, response):
        """Handle rate limits from response headers with proper reset logic"""
        current_time = time.time()

        # Check if we should reset based on time (every 1 second)
        if current_time - self.last_reset_time >= 1:
            self._reset_api_usage()

        if 'X-Shopify-Shop-Api-Call-Limit' in response.headers:
            limit_info = response.headers['X-Shopify-Shop-Api-Call-Limit']
            current_calls, max_limit = map(int, limit_info.split('/'))
            
            # Update max limit if different
            if max_limit != self.max_api_limit:
                self.max_api_limit = max_limit

            # Update current usage
            self.current_api_usage = current_calls
            usage_ratio = self.current_api_usage / self.max_api_limit

            # Reset if we've hit the limit
            if self.current_api_usage >= self.max_api_limit:
                general_logger.warning("API usage limit reached, resetting counter")
                self._reset_api_usage()
                time.sleep(1)  # Wait for a second before continuing
                return

            # Adjust delay based on usage ratio
            if usage_ratio > self.rate_limit_threshold:
                self.default_delay = min(2.0, self.default_delay * 1.5)
                general_logger.warning(f"API usage high ({usage_ratio:.2%}, {current_calls}/{max_limit}), increased delay to {self.default_delay}s")
            elif usage_ratio > 0.5:
                self.default_delay = min(1.0, self.default_delay * 1.2)
                general_logger.info(f"API usage moderate ({usage_ratio:.2%}, {current_calls}/{max_limit}), adjusted delay to {self.default_delay}s")
            else:
                new_delay = max(0.5, self.default_delay * 0.8)
                if new_delay != self.default_delay:
                    self.default_delay = new_delay
                    general_logger.info(f"API usage normal ({usage_ratio:.2%}, {current_calls}/{max_limit}), adjusted delay to {self.default_delay}s")

            # Apply delay
            time.sleep(self.default_delay)

    def _make_request_with_retry(self, method, url, payload=None):
        """Make requests with retry mechanism and proper rate limiting"""
        delay = self.initial_retry_delay
        
        for attempt in range(self.max_retries):
            try:
                if method.lower() == 'get':
                    response = requests.get(url, headers=self.headers)
                else:
                    response = requests.post(url, headers=self.headers, data=json.dumps(payload))

                # Handle rate limits
                self._handle_rate_limits(response)

                # Handle different response codes
                if response.status_code == 200:
                    return response
                
                elif response.status_code == 422:  # Unprocessable Entity
                    crash_logger.error(f"""
                    Request failed - Unprocessable Entity:
                    Status Code: {response.status_code}
                    URL: {url}
                    Response: {response.text}
                    """)
                    return response
                
                elif response.status_code == 429:  # Rate limit exceeded
                    wait_time = int(response.headers.get('Retry-After', delay))
                    crash_logger.warning(f"""
                    Rate limit exceeded:
                    Attempt: {attempt + 1}/{self.max_retries}
                    Waiting: {wait_time} seconds
                    URL: {url}
                    """)
                    time.sleep(wait_time)
                    self._reset_api_usage()  # Reset after rate limit wait
                    continue
                
                elif response.status_code == 404:
                    return response
                
                else:
                    crash_logger.error(f"""
                    Request failed:
                    Status Code: {response.status_code}
                    URL: {url}
                    Response: {response.text}
                    Attempt: {attempt + 1}/{self.max_retries}
                    """)
                    if attempt == self.max_retries - 1:
                        return response
                    time.sleep(delay)
                    delay = min(delay * 2, self.max_retry_delay)

            except requests.exceptions.RequestException as e:
                crash_logger.error(f"""
                Network error:
                Attempt: {attempt + 1}/{self.max_retries}
                Error: {str(e)}
                URL: {url}
                """)
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, self.max_retry_delay)

        return None

    def get_product_id_by_sku(self, sku):
        """Finds a Shopify product ID and inventory item ID using the product's SKU"""
        url = f"https://{self.shop_url}/admin/api/{self.api_version}/products/{sku}.json"
        general_logger.info(f"Searching for product with SKU: {sku}")
        
        try:
            response = self._make_request_with_retry('get', url)
            if response is None:
                crash_logger.error(f"Failed to get product after {self.max_retries} attempts: {sku}")
                return None, None

            if response.status_code == 404:
                crash_logger.warning(f"Product not found: {sku}")
                return None, None

            data = response.json()
            
            if not data.get('product'):
                crash_logger.error(f"Invalid response format for SKU: {sku}")
                return None, None

            variants = data['product']['variants']
            if not variants:
                crash_logger.warning(f"No variants found for product {sku}")
                return None, None

            variant = variants[0]
            product_id = data['product']['id']
            inventory_item_id = variant['inventory_item_id']

            general_logger.info(f"Product found: {sku} (ID: {product_id})")
            return product_id, inventory_item_id

        except Exception as e:
            crash_logger.error(f"Error processing product {sku}: {str(e)}")
            return None, None

    def update_inventory_level(self, inventory_item_id, available_quantity, prod_id):
        """Updates the inventory level of a specific product in Shopify"""
        url = f"https://{self.shop_url}/admin/api/{self.api_version}/inventory_levels/set.json"
        
        payload = {
            "location_id": self.location_id,
            "inventory_item_id": inventory_item_id,
            "available": available_quantity
        }

        general_logger.info(f"Updating inventory for product {prod_id} to {available_quantity}")
        
        try:
            response = self._make_request_with_retry('post', url, payload)
            if response is None:
                crash_logger.error(f"Failed to update inventory after {self.max_retries} attempts: {prod_id}")
                return True

            if response.status_code == 422:
                crash_logger.error(f"""
                Inventory update failed - Tracking not enabled:
                Product ID: {prod_id}
                Response: {response.text}
                """)
                return False  # Don't retry for 422 errors

            if response.status_code == 200:
                current_datetime = datetime.now()
                update_logger.info(f"Inventory updated successfully - Product: {prod_id}, Quantity: {available_quantity}, Time: {current_datetime}")
                return False
            else:
                crash_logger.error(f"Inventory update failed for product {prod_id}: {response.text}")
                return True

        except Exception as e:
            crash_logger.error(f"Error updating inventory for product {prod_id}: {str(e)}")
            return True
