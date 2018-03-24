import os
import enum
import collections


USER_DATE_FORMAT = '%d.%m.%Y'
FILE_DIR = os.path.abspath(os.path.dirname(__file__))

TOKEN = None
with open(os.path.join(FILE_DIR, 'token'), 'r') as f:
    TOKEN = f.readline().strip()

POOLING_TIMEOUT = 10000000000000

OZON_PARTNER_ID = ''
OZON_API_URL = 'https://api.ozon.travel/tours/v1/'
OZON_STATIC_URL = 'https://www.ozon.travel/download/fortour/'
OZON_DATE_FORMAT = '%Y-%m-%d'
OZON_USERNAME = 'foo'
OZON_PASSWORD = 'boo'

REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_DB = 0


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
