import datetime
from redis import StrictRedis

import requests
from transitions import Machine

from .constants import OZON_PARTNER_ID, OZON_API_URL, \
    OZON_DATE_FORMAT, OZON_STATIC_URL, REDIS_HOST, REDIS_PORT, REDIS_DB

redis = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)


class User:
    states = [
        'select_type',
        'select_hotel',
        'select_tour_place',
        'select_place_from',
        'select_date_from',
        'select_date_to',
        'search_success',
        'search_fail',
    ]

    transitions = [
        {
            'trigger': 'to_start',
            'source': '*',
            'dest': 'select_type'
        },
        {
            'trigger': 'to_select_hotel',
            'source': 'select_type',
            'dest': 'select_hotel',
        },
        {
            'trigger': 'to_select_tour_place',
            'source': 'select_type',
            'dest': 'select_tour_place'
        },
        {
            'trigger': 'to_select_place_from',
            'source': ['select_hotel', 'select_tour_place'],
            'dest': 'select_place_from'
        },
        {
            'trigger': 'to_select_date_from',
            'source': 'select_place_from',
            'dest': 'select_date_from'
        },
        {
            'trigger': 'to_select_date_to',
            'source': 'select_date_from',
            'dest': 'select_date_to'
        },
        {
            'trigger': 'to_search_success',
            'source': 'select_date_to',
            'dest': 'search_success'
        },
        {
            'trigger': 'to_search_fail',
            'source': 'select_date_to',
            'dest': 'search_fail'
        },
    ]

    def __init__(self, user_id):
        self.user_id = user_id
        self.machine = Machine(
            model=self,
            states=User.states,
            initial=User.states[0],
            transitions=User.transitions
        )

        self.type = None
        self.place_from = None
        self.place_to = None
        self.date_from = None
        self.date_to = None

    def __gen_key(self, postfix: str):
        return '{}_{}'.format(self.user_id, postfix)

    @staticmethod
    def __set_to_redis(key, value):
        redis.set(key, value)

    @staticmethod
    def __get_from_redis(key):
        return redis.get(key)

    def flush(self):
        self.__set_to_redis(self.__gen_key('state'), self.state)
        self.__set_to_redis(self.__gen_key('type'), self.type)
        self.__set_to_redis(self.__gen_key('place_from'), self.place_from)
        self.__set_to_redis(self.__gen_key('place_to'), self.place_to)
        self.__set_to_redis(self.__gen_key('date_from'), self.date_from)
        self.__set_to_redis(self.__gen_key('date_to'), self.date_to)

    def load(self):
        state = self.__get_from_redis(self.__gen_key('state')).decode()
        if state is not None:
            self.machine.set_state(state)

        self.type = self.__get_from_redis(self.__gen_key('type'))
        self.place_from = self.__get_from_redis(self.__gen_key('place_from'))
        self.place_to = self.__get_from_redis(self.__gen_key('place_to'))
        self.date_from = self.__get_from_redis(self.__gen_key('date_from'))
        self.date_to = self.__get_from_redis(self.__gen_key('date_to'))


class OzonApi:
    def __init__(self):
        pass

    def __post(self, url: str, body: dict=None, timeout: int=10):
        return self.__request(
            method='post',
            url=url,
            json=body,
            timeout=timeout,
        )

    def __get(self, url: str, query: dict=None, timeout: int=10):
        return self.__request(
            method='get',
            url=url,
            params=query,
            timeout=timeout,
        )

    @staticmethod
    def __request(attempts: int=3, **kwargs):
        for _ in range(attempts):
            try:
                return requests.request(**kwargs).json()
            except Exception as e:
                raise e

    def cities(self):
        return self.__get(url=OZON_STATIC_URL + 'departures.json')

    def meal_types(self):
        return self.__get(url=OZON_STATIC_URL + 'MealTypes.json')

    def hotel_list(self):
        return self.__get(url=OZON_STATIC_URL + 'HotelList.json')

    def destinations(self):
        return self.__get(url=OZON_STATIC_URL + 'Destinations.json')

    def search_by_hotel(self,
                        place_from_id: int,
                        hotel_id: int,
                        date_from: datetime.date,
                        date_to: datetime.date,
                        adults: int=1,
                        dynamic_search: bool=False,
                        meta_search: bool=True):
        body = {
            'DepartureCityId': place_from_id,
            'HotelId': hotel_id,
            'DateFrom': date_from.strftime(OZON_DATE_FORMAT),
            'DaysDuration': (date_to - date_from).days,
            'AdultCount': adults,
            'PartnerId': OZON_PARTNER_ID,
            'OnlyDynamicPackages': dynamic_search,
            'MetaSearch': meta_search,
        }
        return self.__post(
            url=OZON_API_URL + 'getOffersByHotel',
            body=body,
        )

    def search_by_place(self,
                        place_from_id: int,
                        place_to_id: int,
                        date_from: datetime.date,
                        date_to: datetime.date,
                        adults: int = 1,
                        dynamic_search: bool = False,
                        meta_search: bool = True):
        body = {
            'DepartureCityId': place_from_id,
            'GeoObjectId': place_to_id,
            'DateFrom': date_from.strftime(OZON_DATE_FORMAT),
            'DaysDuration': (date_to - date_from).days,
            'AdultCount': adults,
            'PartnerId': OZON_PARTNER_ID,
            'OnlyDynamicPackages': dynamic_search,
            'MetaSearch': meta_search,
        }
        return self.__post(
            url=OZON_API_URL + 'getOffersByGeoObject',
            body=body,
        )
