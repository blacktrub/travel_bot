import os


FILE_DIR = os.path.abspath(os.path.dirname(__file__))

TOKEN = None
with open(os.path.join(FILE_DIR, 'token'), 'r') as f:
    TOKEN = f.readline().strip()

POOLING_TIMEOUT = 10000000000000

OZON_PARTNER_ID = ''
OZON_API_URL = 'https://api.ozon.travel/tours/v1/'
OZON_STATIC_URL = 'https://www.ozon.travel/download/fortour/'
OZON_DATE_FORMAT = '%Y-%m-%d'

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
