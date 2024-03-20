import sys
sys.path.append('..')

import os
import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from json import loads
import random
import datetime
import mysql.connector
import boto3
from logging.handlers import RotatingFileHandler

# env
KAFKA_SERVER = os.getenv('KAFKA_SERVER')
SHIPPING_TOPIC = os.getenv('SHIPPING_TOPIC')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')
ACCOUNTING_LOG_BUCKET = os.getenv('ACCOUNTING_LOG_BUCKET')

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Create a file handler to log errors
file_handler = RotatingFileHandler('accounting.log', maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# upload logs to S3
class S3Handler(logging.StreamHandler):
    def __init__(self, bucket_name, key):
        super().__init__()
        self.bucket_name = bucket_name
        self.key = key
        self.s3_client = boto3.client('s3')

    def emit(self, record):
        log_entry = self.format(record) + '\n'
        self.upload_log(log_entry)

    def upload_log(self, log_entry):
        self.s3_client.put_object(Body=log_entry, Bucket=self.bucket_name, Key=self.key)

# Create an instance of the S3Handler
s3_handler = S3Handler(bucket_name=ACCOUNTING_LOG_BUCKET, key='accounting.log')
s3_handler.setLevel(logging.ERROR)
logger.addHandler(s3_handler)


# MySQL connection
mysql_conn = mysql.connector.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE
)
mysql_cursor = mysql_conn.cursor()

# Kafka consumers
shipping_consumer = KafkaConsumer(
    SHIPPING_TOPIC,
    bootstrap_servers=[KAFKA_SERVER],
    value_deserializer=lambda x: loads(x.decode('utf-8')))

for shipping_message in shipping_consumer:
    try:
        shipping_data = shipping_message.value

        invoice = shipping_data.get('Invoice/Item Number', '')
        shipping_cost = shipping_data.get('Shipping Cost', '')
        sales = shipping_data.get('sales', '')

        # MySQL
        LEDGER_CREDIT = """
            INSERT INTO ledger (InvoiceItemNumber, credit, note)
            VALUES (%s, %s, 'sale')
        """

        LEDGER_DEBIT = """
            INSERT INTO ledger (InvoiceItemNumber, debit, note)
            VALUES (%s, %s, 'shipping')
        """
        credit_data = (invoice, sales)
        mysql_cursor.execute(LEDGER_CREDIT, credit_data)

        shipping_expense = float(shipping_cost) * -1
        debit_data = (invoice, shipping_expense)
        mysql_cursor.execute(LEDGER_DEBIT, debit_data)

        mysql_conn.commit()
    except Exception as e:
        logger.error(f"Error processing message: {e}")

mysql_cursor.close()
mysql_conn.close()