import os
import enum
import collections

from urllib import parse


MAX_RESULTS = 1

USER_DATE_FORMAT = '%d.%m.%Y'
FILE_DIR = os.path.abspath(os.path.dirname(__file__))

TOKEN = os.environ.get('TOKEN')

POOLING_TIMEOUT = 10000000000000

OZON_PARTNER_ID = os.environ.get('OZON_PARTNER_ID')
OZON_API_URL = 'https://api.ozon.travel/tours/v1/'
OZON_STATIC_URL = 'https://www.ozon.travel/download/fortour/'
OZON_DATE_FORMAT = '%Y-%m-%d'
OZON_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
OZON_USERNAME = os.environ.get('OZON_USERNAME')
OZON_PASSWORD = os.environ.get('OZON_PASSWORD')
OZON_AUTH = OZON_USERNAME + ':' + OZON_PASSWORD

REDIS_URL = os.environ.get('REDIS_URL')

DB_URL = parse.urlparse(os.environ["DATABASE_URL"])

DB_NAME = DB_URL.path[1:]
DB_USERNAME = DB_URL.username
DB_PASSWORD = DB_URL.password
DB_HOST = DB_URL.hostname
DB_PORT = DB_URL.port


class UserStates(enum.Enum):
    SELECT_TYPE = 'select_type'
    SELECT_HOTEL = 'select_hotel'
    SELECT_TOUR_PLACE = 'select_tour_place'
    SELECT_PLACE_FROM = 'select_place_from'
    SELECT_DATE_FROM = 'select_date_from'
    SELECT_DATE_TO = 'select_date_to'
    SEARCH_SUCCESS = 'search_success'
    SEARCH_FAIL = 'search_fail'

    @classmethod
    def as_list(cls):
        return [v.value for k, v in cls.__members__.items()]


class SearchType(enum.Enum):
    CITY = 'По городу'
    HOTEL = 'По отелю'

City = collections.namedtuple('City', 'name id')
Hotel = collections.namedtuple('Hotel', 'name id')
Tour = collections.namedtuple('Tour', 'name id url date_from days price')
