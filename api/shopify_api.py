import requests
import json
import time
from datetime import datetime
import logging
import os
from utils.logger_config import setup_logger

general_logger = setup_logger('general_logger')
crash_logger = setup_logger('crash_logger')
update_logger = setup_logger('update_logger')

class ShopifyAPI:
    def __init__(self, access_token=None, shop_url=None, location_id=None):
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
        self.default_delay = 0.5  # Default delay between requests to stay within rate limits
        self.api_version = '2023-04'

    def get_product_id_by_sku(self, sku):
        """Finds a Shopify product ID and inventory item ID using the product's SKU"""
        url = f"https://{self.shop_url}/admin/api/{self.api_version}/products.json?sku={sku}"
        
        try:
            response = requests.get(url, headers=self.headers)
            products = response.json()
            
            if response.status_code == 200 and products.get('products'):
                print("Product Found")
                print("inventory_quantity: ", products['products'][0]['variants'][0]['inventory_quantity'])
                return products['products'][0]['id'], products['products'][0]['variants'][0]['inventory_item_id']
            else:
                print(response.status_code)
                print("Product Not Found")
                return None, None
                
        except Exception as e:
            crash_logger.error(f"Error getting product ID for SKU {sku}: {str(e)}")
            print(response.status_code)
            print("Product Not Found")
            return None, None

    def update_inventory_level(self, inventory_item_id, available_quantity, prod_id):
        """Updates the inventory level of a specific product in Shopify with rate limit handling"""
        url = f"https://{self.shop_url}/admin/api/{self.api_version}/inventory_levels/set.json"
        
        payload = {
            "location_id": self.location_id,
            "inventory_item_id": inventory_item_id,
            "available": available_quantity
        }

        # Exponential backoff parameters
        max_retries = 5
        delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=self.headers, data=json.dumps(payload))
                
                # Check rate limit headers
                if 'X-Shopify-Shop-Api-Call-Limit' in response.headers:
                    limit_info = response.headers['X-Shopify-Shop-Api-Call-Limit']
                    current_usage, max_limit = map(int, limit_info.split('/'))
                    usage_ratio = current_usage / max_limit

                    if usage_ratio > 0.8:
                        self.default_delay = min(2, self.default_delay + 0.5)
                    elif usage_ratio < 0.5:
                        self.default_delay = max(0.5, self.default_delay - 0.1)

                # Success case
                if response.status_code == 200:
                    print("Inventory level updated successfully for product:", prod_id)
                    
                    # Get current date and time
                    current_datetime = datetime.now()
                    print("Inventory level updated at: ", current_datetime)
                    
                    # Log successful update to file
                    with open("updated_products.txt", "a") as log_file:
                        log_file.write(f"Product ID: {prod_id}, Inventory: {available_quantity}, Updated at: {current_datetime}\n")
                    
                    update_logger.info(f"Inventory level updated successfully for product: {prod_id}")
                    return False

                # Handle 429 Rate Limit Error
                elif response.status_code == 429:
                    print(f"Rate limit exceeded on attempt {attempt + 1} of {max_retries}. Retrying in {delay} seconds.")
                    time.sleep(delay)
                    delay *= 2
                    continue

                # Log other errors
                else:
                    print(f"Failed to update inventory level. Error: {response.status_code} : {response.text}")
                    crash_logger.error(f"Failed to update inventory level. Error: {response.status_code} : {response.text}")
                    return True

            except Exception as e:
                crash_logger.error(f"Error updating inventory level for product {prod_id}: {str(e)}")
                continue

        # Log failure after max retries
        print("Failed to update inventory level after max retries for product:", prod_id)
        crash_logger.error(f"Failed to update inventory level after max retries for product: {prod_id}")
        return True
