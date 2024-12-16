import os
import glob
from datetime import datetime
from api.clf_api import CLFAPI
from api.shopify_api import ShopifyAPI
from utils.logger_config import setup_logger
from utils.file_utils import load_dictionary
from utils.email_utils import EmailSender

# Setup loggers
general_logger = setup_logger('general_logger')
crash_logger = setup_logger('crash_logger')
update_logger = setup_logger('update_logger')

def count_crash_logs(start_date_str):
    """
    Count the number of ERROR and WARNING entries in today's crash log file.
    Returns a dictionary with counts for each type of log entry.
    """
    try:
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            general_logger.info("Created logs directory")
            return {'errors': 0, 'warnings': 0, 'total': 0}

        # Look for today's crash log file
        crash_log_files = glob.glob(os.path.join(logs_dir, f'CRASH_LOGS_*{start_date_str}*.txt'))
        if not crash_log_files:
            general_logger.info("No crash log files found for today")
            return {'errors': 0, 'warnings': 0, 'total': 0}

        # Count errors and warnings in the latest crash log file
        error_count = 0
        warning_count = 0
        
        with open(crash_log_files[0], 'r') as f:
            for line in f:
                if ' ERROR ' in line:  # Space before and after to ensure exact match
                    error_count += 1
                elif ' WARNING ' in line:  # Space before and after to ensure exact match
                    warning_count += 1

        total_count = error_count + warning_count
        
        stats = {
            'errors': error_count,
            'warnings': warning_count,
            'total': total_count
        }
        
        general_logger.info(f"""
        Crash Log Statistics:
        Errors: {error_count}
        Warnings: {warning_count}
        Total: {total_count}
        """)
        
        return stats
        
    except Exception as e:
        crash_logger.error(f"Error counting crash logs: {str(e)}")
        return {'errors': 0, 'warnings': 0, 'total': 0}
    
def main():
    
    start_time = datetime.now()
    start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    start_date_str_crash_logs = start_time.strftime('%Y%m%d')  # Format for crash logs
    general_logger.info(f"Script started at: {start_time_str}")
    
    
    # Initialize API clients
    clf_api = CLFAPI()
    shopify_api = ShopifyAPI()
    email_sender = EmailSender()

    # Load product dictionary
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    productId_sku_dict = load_dictionary(os.path.join(data_dir, "C:\\Users\\murtaza\\Desktop\\CLF_SHOPIFY SCRIPTS\\New_codes\\productId_sku_dict.json"))
    keylist = list(productId_sku_dict.keys())
    vallist = list(productId_sku_dict.values())

    updated_prods = []
    
    try:
        general_logger.info("Starting stock update process")
        
        # Get authentication token and product codes
        skus = clf_api.get_product_codes()
        if not skus:
            crash_logger.error("Failed to retrieve product codes")
            if clf_api.token_generation_count >= clf_api.MAX_TOKEN_ATTEMPTS:
                end_time = datetime.now()
                end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
                runtime = end_time - start_time
                
                crash_stats = count_crash_logs(start_date_str_crash_logs)  # Pass formatted date
                stats = {
                    'start_time': start_time_str,
                    'end_time': end_time_str,
                    'runtime': str(runtime),
                    'products_updated': len(updated_prods),
                    'error_count': crash_stats['errors'],
                    'warning_count': crash_stats['warnings'],
                    'total_issues': crash_stats['total']
                }
                # Pass start_time_str to the email sender
                email_sender.send_token_limit_email(stats, start_time_str)
                general_logger.error("Token generation limit exceeded. Script stopped.")
            return
            
        general_logger.info(f"Retrieved {len(skus)} SKUs to process")
        
        # Process each SKU
        for values in skus:
            try:
                # Get stock level and product data
                inv_qty = clf_api.get_product_stock(values)
                barcode = clf_api.get_product_barcode(values)
                
                # Update Shopify inventory if barcode exists
                if barcode in productId_sku_dict.values():
                    # Get Shopify product details
                    product_id_to_update, inventory_item_id = shopify_api.get_product_id_by_sku(
                        keylist[vallist.index(barcode)]
                    )
                    
                    if product_id_to_update is not None and inventory_item_id is not None:
                        # Attempt to update inventory
                        is_updated = shopify_api.update_inventory_level(
                            inventory_item_id, 
                            inv_qty, 
                            product_id_to_update
                        )
                        
                        # Add to updated products list only if update was successful
                        if not is_updated:
                            updated_prods.append(keylist[vallist.index(barcode)])
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
                
          # Get crash log statistics
        crash_stats = count_crash_logs(start_date_str_crash_logs)  # Pass formatted date
        
        # Calculate final times
        end_time = datetime.now()
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        runtime = end_time - start_time
        
        # Send completion email with detailed stats
        stats = {
            'start_time': start_time_str,
            'end_time': end_time_str,
            'runtime': str(runtime),
            'products_updated': len(updated_prods),
            'error_count': crash_stats['errors'],
            'warning_count': crash_stats['warnings'],
            'total_issues': crash_stats['total'],
            'total_skus': len(skus)
        }       
        # Pass start_time_str to the email sender
        email_sender.send_completion_email(stats, start_time_str)
        general_logger.info(f"""
        Stock update process completed:
        Start Time: {start_time_str}
        End Time: {end_time_str}
        Runtime: {runtime}
        Products Updated: {len(updated_prods)}
        Total SKUs Processed: {len(skus)}
        Errors: {crash_stats['errors']}
        Warnings: {crash_stats['warnings']}
        """)
        general_logger.info("Stock update process completed successfully")
                
    except Exception as e:
        crash_logger.error(f"""
        Critical Error:
        Error Type: {type(e).__name__}
        Error Details: {str(e)}
        """)
        # Send completion email with stats even if there's an error
        end_time = datetime.now()
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        runtime = end_time - start_time
        
        crash_stats = count_crash_logs(start_date_str_crash_logs)  # Pass formatted date
        stats = {
            'start_time': start_time_str,
            'end_time': end_time_str,
            'runtime': str(runtime),
            'products_updated': len(updated_prods),
            'error_count': crash_stats['errors'],
            'warning_count': crash_stats['warnings'],
            'total_issues': crash_stats['total'],
            'total_skus': len(skus) if 'skus' in locals() else 0
        }
        # Pass start_time_str to the email sender
        email_sender.send_completion_email(stats, start_time_str)
    finally:
        end_time = datetime.now()
        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
        general_logger.info(f"Script ended at: {end_time_str}")
        
        # Clean up old log files
        try:
            from utils.logs_deletion import LogsCleaner
            cleaner = LogsCleaner(retention_days=2)
            cleaner.clean_old_logs()
        except Exception as e:
            general_logger.error(f"Error during logs cleanup: {str(e)}")


if __name__ == "__main__":
    main()
