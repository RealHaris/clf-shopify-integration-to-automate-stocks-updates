import requests
import xml.etree.ElementTree as ET
from requests.exceptions import RequestException
from datetime import datetime
import logging
import json
import os
from utils.logger_config import setup_logger
from utils.email_utils import EmailSender

general_logger = setup_logger('general_logger')
crash_logger = setup_logger('crash_logger')

class CLFAPI:
    MAX_TOKEN_ATTEMPTS = 20

    def __init__(self, base_url=None):
        # Load credentials from JSON file
        credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'credentials.json')
        with open(credentials_path, 'r') as f:
            credentials = json.load(f)['clf']
            print(credentials)
        
        self.base_url = base_url or credentials['base_url']
        self.headers = {'content-type': 'text/xml'}
        self.username = credentials['username']
        self.password = credentials['password']
        self.auth_token = None
        self.token_generation_count = 0
        self.email_sender = EmailSender()

    def check_auth_error(self, tree):
        """Checks if response contains authentication error and returns True if token needs refresh"""
        try:
            namespace = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                'clf': 'http://services.clfdistribution.com/CLFWebOrdering'
            }
            error_message = tree.find('.//clf:WebServiceHeader/clf:ErrorMessage', namespace)
            if error_message is not None and error_message.text == "Please call GetAuthenticationToken() first":
                crash_logger.error("Authentication token expired, will refresh and retry")
                return True
            return False
        except Exception:
            return False

    def get_authentication_token(self):
        """Retrieves an authentication token from CLF web service using provided credentials"""
        # Check token generation limit
        if self.token_generation_count >= self.MAX_TOKEN_ATTEMPTS:
            crash_logger.error("Token generation limit exceeded")
            return None

        self.token_generation_count += 1
        operation_start_time = datetime.now()
        general_logger.info(f"Starting authentication token retrieval (Attempt {self.token_generation_count}/{self.MAX_TOKEN_ATTEMPTS})")

        payload = '''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xmlns:xsd="http://www.w3.org/2001/XMLSchema">
                    <soap:Header>
                    <WebServiceHeader xmlns="http://services.clfdistribution.com/CLFWebOrdering" />
                    </soap:Header>
                    <soap:Body>
                    <GetAuthenticationToken xmlns="http://services.clfdistribution.com/CLFWebOrdering">
                    <Username>{}</Username>
                    <Password>{}</Password>
                    </GetAuthenticationToken>
                    </soap:Body>
                    </soap:Envelope>'''.format(self.username, self.password)

        try:
            response = requests.post(self.base_url, data=payload, headers=self.headers)
            general_logger.info(f"Authentication request sent. Status code: {response.status_code}")

            if response.status_code == 200:
                try:
                    tree = ET.fromstring(response.content)
                    namespace = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                               'clf': 'http://services.clfdistribution.com/CLFWebOrdering'}

                    token_element = tree.find('.//clf:GetAuthenticationTokenResult', namespace)
                    self.auth_token = token_element.text if token_element is not None else None
                    
                    if self.auth_token:
                        general_logger.info("Authentication token retrieved successfully")
                        return self.auth_token
                    else:
                        crash_logger.error("Authentication token not found in response")
                        return None
                        
                except ET.ParseError as e:
                    crash_logger.error(f"""
                    Authentication XML Parsing Error:
                    Time: {operation_start_time}
                    Error: {str(e)}
                    Response: {response.content[:200]}... (truncated)
                    """)
                    return None
            else:
                crash_logger.error(f"""
                Authentication Request Failed:
                Time: {operation_start_time}
                Status Code: {response.status_code}
                Response: {response.text[:200]}... (truncated)
                """)
                return None
                
        except RequestException as e:
            crash_logger.error(f"""
            Authentication Network Error:
            Time: {operation_start_time}
            Error Type: {type(e).__name__}
            Error Details: {str(e)}
            """)
            return None

    def get_product_codes(self):
        """Fetches all available product codes from CLF using the authentication token"""
        if not self.auth_token:
            self.auth_token = self.get_authentication_token()
            if not self.auth_token:
                if self.token_generation_count >= self.MAX_TOKEN_ATTEMPTS:
                    crash_logger.error("Maximum token generation attempts reached. Stopping script.")
                    return None
        
        operation_start_time = datetime.now()
        general_logger.info(f"Starting product codes retrieval operation at {operation_start_time}")
        
        payload = '''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xmlns:xsd="http://www.w3.org/2001/XMLSchema">
                    <soap:Header>
                    <WebServiceHeader xmlns="http://services.clfdistribution.com/CLFWebOrdering">
                    <AuthenticationToken>{}</AuthenticationToken>
                    </WebServiceHeader>
                    </soap:Header>
                    <soap:Body>
                    <GetProductCodes xmlns="http://services.clfdistribution.com/CLFWebOrdering" />
                    </soap:Body>
                    </soap:Envelope>'''.format(self.auth_token)

        try:
            general_logger.info("Sending SOAP request to CLF API")
            response = requests.post(self.base_url, data=payload, headers=self.headers)
            general_logger.info(f"Received response with status code: {response.status_code}")

            if response.status_code == 200:
                try:
                    tree = ET.fromstring(response.content)                    
                    if self.check_auth_error(tree):
                        self.auth_token = self.get_authentication_token()
                        if self.auth_token:
                            return self.get_product_codes()
                        return []
                    
                    namespace = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                               'clf': 'http://services.clfdistribution.com/CLFWebOrdering'}

                    product_codes_element = tree.find('.//clf:GetProductCodesResult', namespace)
                    if product_codes_element is not None and product_codes_element.text is not None:
                        product_codes = product_codes_element.text

                        product_codes_tree = ET.fromstring(product_codes)
                        code_elements = product_codes_tree.findall('.//Code')

                        clf_product_codes = [code_element.find('sku').text for code_element in code_elements]
                        
                        general_logger.info(f"Successfully retrieved {len(clf_product_codes)} product codes")
                        return clf_product_codes
                    else:
                        general_logger.warning("No Product Codes Found")
                        return []
                        
                except ET.ParseError as e:
                    crash_logger.error(f"XML Parsing Error in get_product_codes: {str(e)}")
                    return []
            else:
                crash_logger.error(f"API Request Failed with status code: {response.status_code}")
                return []
                
        except RequestException as e:
            crash_logger.error(f"Network Error in get_product_codes: {str(e)}")
            return []

    def get_product_stock(self, product_code):
        """Gets current stock level for a specific product from CLF inventory"""
        if not self.auth_token:
            self.auth_token = self.get_authentication_token()
            if not self.auth_token:
                return None

        operation_start_time = datetime.now()
        general_logger.info(f"Retrieving stock for product code: {product_code}")

        payload = '''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xmlns:xsd="http://www.w3.org/2001/XMLSchema">
                    <soap:Header>
                    <WebServiceHeader xmlns="http://services.clfdistribution.com/CLFWebOrdering">
                    <AuthenticationToken>{}</AuthenticationToken>
                    </WebServiceHeader>
                    </soap:Header>
                    <soap:Body>
                    <GetProductStock xmlns="http://services.clfdistribution.com/CLFWebOrdering">
                    <productCodesXml>&lt;ProductCodes&gt;&lt;Code&gt;{}&lt;/Code&gt;&lt;/ProductCodes&gt;</productCodesXml>
                    </GetProductStock>
                    </soap:Body>
                    </soap:Envelope>'''.format(self.auth_token, product_code)

        try:
            response = requests.post(self.base_url, data=payload, headers=self.headers)
            
            if response.status_code == 200:
                try:
                    tree = ET.fromstring(response.content)
                    
                    if self.check_auth_error(tree):
                        print("Authentication token expired, will refresh and retry")
                        self.auth_token = self.get_authentication_token()
                        if self.auth_token:
                            return self.get_product_stock(product_code)
                        return None

                    namespace = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                               'clf': 'http://services.clfdistribution.com/CLFWebOrdering'}
                    
                    result_element = tree.find('.//clf:GetProductStockResult', namespace)
                    if result_element is None or not result_element.text:
                        crash_logger.error(f"No GetProductStockResult element found for product: {product_code}")
                        return None

                    try:
                        stock_tree = ET.fromstring(result_element.text)
                    except ET.ParseError as e:
                        crash_logger.error(f"""
                        Stock XML Inner Parsing Error for product {product_code}:
                        Error: {str(e)}
                        Result Content: {result_element.text[:200]}... (truncated)
                        """)
                        return None

                    # First try to find stock in the Product element
                    product = stock_tree.find('.//Product')
                    if product is not None:
                        stock_element = product.find('stock')
                        if stock_element is not None and stock_element.text:
                            try:
                                stock_level = int(stock_element.text.strip())
                                general_logger.info(f"Stock level for product {product_code}: {stock_level}")
                                return stock_level
                            except ValueError as e:
                                crash_logger.error(f"Invalid stock value for product {product_code}: {stock_element.text}")
                                return None

                    # If not found in Product, try direct stock element
                    stock_element = stock_tree.find('.//stock')
                    if stock_element is not None and stock_element.text:
                        try:
                            stock_level = int(stock_element.text.strip())
                            general_logger.info(f"Stock level for product {product_code}: {stock_level}")
                            return stock_level
                        except ValueError as e:
                            crash_logger.error(f"Invalid stock value for product {product_code}: {stock_element.text}")
                            return None
                    
                    crash_logger.error(f"Stock Level Not Found for product: {product_code}")
                    return None
                    
                except ET.ParseError as e:
                    crash_logger.error(f"""
                    Stock XML Parsing Error for product {product_code}:
                    Error: {str(e)}
                    Response Content: {response.content[:200]}... (truncated)
                    """)
                    return None
            else:
                crash_logger.error(f"""
                Stock Request Failed for product {product_code}:
                Status Code: {response.status_code}
                Response: {response.text[:200]}... (truncated)
                """)
                return None
                
        except RequestException as e:
            crash_logger.error(f"""
            Stock Network Error for product {product_code}:
            Error Type: {type(e).__name__}
            Error Details: {str(e)}
            """)
            return None

    def get_product_price_and_barcode(self, product_code):
        """Retrieves price and barcode information for a specific product from CLF"""
        if not self.auth_token:
            print("Authentication token not found, will refresh and retry")
            self.auth_token = self.get_authentication_token()
            if not self.auth_token:
                return None, None

        operation_start_time = datetime.now()
        general_logger.info(f"Retrieving price and barcode for product code: {product_code}")

        namespace = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                    'clf': 'http://services.clfdistribution.com/CLFWebOrdering'}
        
        payload = '''<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
                    <soap:Header>
                        <WebServiceHeader xmlns="http://services.clfdistribution.com/CLFWebOrdering">
                            <AuthenticationToken>{}</AuthenticationToken>
                        </WebServiceHeader>
                    </soap:Header>
                    <soap:Body>
                        <GetProductData xmlns="http://services.clfdistribution.com/CLFWebOrdering">
                            <productCodesXml>&lt;ProductCodes&gt;&lt;Code&gt;{}&lt;/Code&gt;&lt;/ProductCodes&gt;</productCodesXml>
                        </GetProductData>
                    </soap:Body>
                </soap:Envelope>'''.format(self.auth_token, product_code)

        try:
            response = requests.post(self.base_url, data=payload, headers=self.headers)
            
            if response.status_code == 200:
                try:
                    tree = ET.fromstring(response.content)
                    
                    if self.check_auth_error(tree):
                        self.auth_token = self.get_authentication_token()
                        if self.auth_token:
                            return self.get_product_price_and_barcode(product_code)
                        return None, None

                    namespace2 = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                            'clf': 'http://services.clfdistribution.com/CLFWebOrdering'}

                    product_data = tree.find('.//clf:GetProductDataResult', namespace2)

                    if product_data is not None and product_data.text is not None:
                        product_data = product_data.text
                        product_tree = ET.fromstring(product_data)
                        products = product_tree.findall('.//Product')
                        
                        if products is not None:
                            for product in products:
                                price_elem = product.find('msrp')
                                barcode_elem = product.find('barcode')
                                
                                price = price_elem.text if price_elem is not None else None
                                barcode = barcode_elem.text if barcode_elem is not None else None
                                
                                if price is not None and barcode is not None:
                                    general_logger.info(f"Retrieved data for product {product_code} - Price: {price}, Barcode: {barcode}")
                                    return price, barcode
                                else:
                                    crash_logger.error(f"""
                                    Missing price or barcode:
                                    Time: {operation_start_time}
                                    Product Code: {product_code}
                                    """)
                        
                        crash_logger.error(f"""
                        No Product Data Found:
                        Time: {operation_start_time}
                        Product Code: {product_code}
                        """)
                        return None, None
                    
                except ET.ParseError as e:
                    crash_logger.error(f"Product Data XML Parsing Error for {product_code}: {str(e)}")
                    return None, None
            else:
                crash_logger.error(f"Product Data Request Failed for {product_code}. Status: {response.status_code}")
                return None, None
                
        except RequestException as e:
            crash_logger.error(f"Product Data Network Error for {product_code}: {str(e)}")
            return None, None
