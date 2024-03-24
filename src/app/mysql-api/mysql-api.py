import sys
import os
import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from json import loads
import random
from datetime import datetime
import mysql.connector
import boto3
from logging.handlers import RotatingFileHandler

# env
KAFKA_SERVER = os.getenv('KAFKA_SERVER')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')

# Create a logger
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)

# Create a RotatingFileHandler
file_handler = RotatingFileHandler('example.log', maxBytes=10000, backupCount=5)
file_handler.setLevel(logging.DEBUG)

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Attach the handler to the logger
logger.addHandler(file_handler)

# Log messages
logger.debug('Debug message')
logger.info('Info message')
logger.warning('Warning message')
logger.error('Error message')
logger.critical('Critical message')

# MySQL connection
mysql_conn = mysql.connector.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE
)

mysql_cursor = mysql_conn.cursor()

# Create a consumer instance
consumer = KafkaConsumer(
    'mysql',
bootstrap_servers=[KAFKA_SERVER],
    auto_offset_reset='earliest',  # Start consuming from the earliest offset
    enable_auto_commit=True,       # Automatically commit offsets
    group_id='oaken_mysql_group',  # Specify a consumer group
    value_deserializer=lambda x: loads(x.decode('utf-8')))

consumer.subscribe(topics=['mysql'])

invoice_producer = KafkaProducer(bootstrap_servers=[KAFKA_SERVER],
                        value_serializer=lambda x: json.dumps(x).encode('utf-8'))

print('set up complete')
# Poll for messages
try:
    for message in consumer:
        try:
            data = message.value
            # Customer
            storNumber = int(data.get('StoreNumber', ''))
            if not storNumber:
                pass

            storeName = data.get('StoreName', '')
            address = data.get('Address', '')
            city = data.get('City', '')
            county = data.get('County', '')
            state = data.get('State', '')
            zip_code = int(data.get('ZipCode', ''))

            # vendor
            vendorNumber = int(float(data.get('VendorNumber', '')))
            if not vendorNumber:
                pass

            vendorName = data.get('VendorName', '')

            # category
            category = int(float(data.get('Category','')))
            if not category:
                pass

            categoryName = (data.get('CategoryName',''))

            # product
            itemNumber = int(data.get('ItemNumber', ''))
            if not itemNumber:
                pass
            itemDescription = data.get('ItemDescription', '')
            pack = int(data.get('Pack', ''))
            volume = int(data.get('BottleVolumeML', ''))
            cost = float(data.get('BottleCost', '').replace('$', ''))
            retail = float(data.get('BottleRetail', '').replace('$', ''))

            # Sales
            invoice = data.get('Invoice', '')
            if not invoice:
                pass

            date_str = data.get('Date', '')
            if not date_str:
                pass

            sales_date = datetime.datetime.strptime(date_str, '%m/%d/%Y').date()

            amountSold = int(data.get('BottlesSold', ''))
            totalLiters = float(data.get('VolumeSoldLiters', ''))

            sales_str = data.get('SaleDollars', '').replace('$', '')
            sales = float(sales_str)

            # MySQL
            '''
            Multiple try/except blocks are used due to the simplistic invoicing
            application script.

            In a real world scenario, likely each of these blocks would be done
            as a truly separate process.

            The try/except prevents the duplicates failing to be added to the
            database from preventing the rest of the processes from competing.
            '''

            try:
                CUSTOMER_QUERY = '''
                    INSERT INTO customer (StoreNumber,StoreName,Address,City,CountyName,State,ZipCode)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    '''
                customer_data = (storNumber,storeName,address,city,county,state,zip_code)
                mysql_cursor.execute(CUSTOMER_QUERY, customer_data)
                mysql_conn.commit()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                pass

            try:
                VENDOR_QUERY = '''
                    INSERT INTO vendor (VendorNumber,VendorName)
                    VALUES (%s,%s)
                    '''
                vendor_data = (vendorNumber,vendorName)
                mysql_cursor.execute(VENDOR_QUERY,vendor_data)
                mysql_conn.commit()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                pass

            try:
                CATEGORY_QUERY = '''
                    INSERT INTO category (CategoryNumber,CategoryName)
                    VALUES (%s,%s)
                    '''
                category_data = (category,categoryName)
                mysql_cursor.execute(CATEGORY_QUERY, category_data)
                mysql_conn.commit()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                pass

            try:
                PRODUCT_QUERY = '''
                    INSERT INTO product (ItemNumber,CategoryNumber,ItemDescription,BottleVolumeML,
                    Pack,BottleCost,BottleRetail)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    '''
                product_data = (itemNumber,category,itemDescription,volume,pack,cost,retail)
                mysql_cursor.execute(PRODUCT_QUERY, product_data)
                mysql_conn.commit()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                pass

            try:
                SALES_QUERY = '''
                INSERT INTO sales (Invoice,StoreNumber,VendorNumber,SaleDate,SaleDollars,
                ItemNumber,VolumeSoldLiters,BottlesSold)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                '''
                sales_data = (invoice,storNumber,vendorNumber,sales_date,sales,itemNumber,
                                totalLiters,amountSold)
                mysql_cursor.execute(SALES_QUERY, sales_data)
                mysql_conn.commit()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                pass

            # Topic should post after MySQL processing to ensure data is in the database.
            try:
                sales_date_str = str(sales_date)
                INVOICES_info = {
                    "Invoice": invoice,
                    "SaleDate": date_str,
                    "saleDollars": sales_str
                }

                invoice_producer.send('invoices', value=INVOICES_info)
                invoice_producer.flush()
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                pass

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            pass

    # Close the consumer
finally:
    consumer.close()
    mysql_conn.close()