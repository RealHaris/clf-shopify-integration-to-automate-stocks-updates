from api.clf_api import CLFAPI
from api.shopify_api import ShopifyAPI
from utils.logger_config import setup_logger
from utils.file_utils import load_dictionary, save_list
from utils.email_utils import EmailSender
import time
import os
import glob

# Setup loggers
general_logger = setup_logger('general_logger')
crash_logger = setup_logger('crash_logger')
update_logger = setup_logger('update_logger')

# Initialize API clients
clf_api = CLFAPI()
shopify_api = ShopifyAPI()
email_sender = EmailSender()

# Load product dictionary
data_dir = os.path.join(os.path.dirname(__file__), 'data')
productId_sku_dict = load_dictionary(os.path.join(data_dir, "productId_sku_dict.json"))
keylist = list(productId_sku_dict.keys())
vallist = list(productId_sku_dict.values())

def count_crash_logs():
    """Count the number of crash logs in today's log file"""
    try:
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            general_logger.info("Created logs directory")
            return 0

        # Look for today's crash log file
        crash_log_files = glob.glob(os.path.join(logs_dir, f'crash_*{time.strftime("%Y-%m-%d")}*.log'))
        if not crash_log_files:
            general_logger.info("No crash log files found for today")
            return 0

        # Count errors in the latest crash log file
        with open(crash_log_files[0], 'r') as f:
            return sum(1 for line in f if 'ERROR' in line)
    except Exception as e:
        general_logger.error(f"Error counting crash logs: {str(e)}")
        return 0

def main():
    updated_prods = []
    
    try:
        general_logger.info("Starting stock update process")
        
        # Get authentication token and product codes
        skus = clf_api.get_product_codes()
        if not skus:
            crash_logger.error("Failed to retrieve product codes")
            if clf_api.token_generation_count >= clf_api.MAX_TOKEN_ATTEMPTS:
                stats = {
                    'products_updated': len(updated_prods),
                    'crash_logs': count_crash_logs()
                }
                email_sender.send_token_limit_email(stats)
                general_logger.error("Token generation limit exceeded. Script stopped.")
            return
            
        general_logger.info(f"Retrieved {len(skus)} SKUs to process")
        
        # Process each SKU
        for values in skus:
            try:
                # Get stock level and product data
                inv_qty = clf_api.get_product_stock(values)
                price, barcode = clf_api.get_product_price_and_barcode(values)
                print(price, barcode)
                
                # Update Shopify inventory
                if barcode in productId_sku_dict.values():
                    # Get Shopify product details
                    product_id_to_update, inventory_item_id = shopify_api.get_product_id_by_sku(
                        keylist[vallist.index(barcode)]
                    )
                    
                    if product_id_to_update is not None and inventory_item_id is not None:
                        updated_prods.append(keylist[vallist.index(barcode)])
                        is_not_updated = shopify_api.update_inventory_level(
                            inventory_item_id, 
                            inv_qty, 
                            product_id_to_update
                        )
                        
                        # Retry once if update failed
                        if is_not_updated:
                            general_logger.info(f"Retrying update after 60s delay for product: {product_id_to_update}")
                            time.sleep(60)
                            shopify_api.update_inventory_level(
                                inventory_item_id,
                                inv_qty,
                                product_id_to_update
                            )
                    else:
                        crash_logger.error(f"Failed to get product/inventory IDs for barcode: {barcode}")
                else:
                    general_logger.warning(f"Barcode not found in product dictionary: {barcode}")
                    
            except Exception as e:
                crash_logger.error(f"""
                Processing Error:
                SKU: {values}
                Error Type: {type(e).__name__}
                Error Details: {str(e)}
                """)
                
        # Send completion email with stats
        stats = {
            'products_updated': len(updated_prods),
            'crash_logs': count_crash_logs()
        }
        email_sender.send_completion_email(stats)
        general_logger.info("Stock update process completed successfully")
                
    except Exception as e:
        crash_logger.error(f"""
        Critical Error:
        Error Type: {type(e).__name__}
        Error Details: {str(e)}
        """)
        # Send completion email with stats even if there's an error
        stats = {
            'products_updated': len(updated_prods),
            'crash_logs': count_crash_logs()
        }
        email_sender.send_completion_email(stats)

if __name__ == "__main__":
    main()
