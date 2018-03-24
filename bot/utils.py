import datetime

import requests
from requests.auth import HTTPBasicAuth
from transitions import Machine
from redis import StrictRedis
import peewee

from .constants import OZON_PARTNER_ID, OZON_API_URL, \
    OZON_DATE_FORMAT, OZON_STATIC_URL, OZON_USERNAME, OZON_PASSWORD, \
    REDIS_HOST, REDIS_PORT, REDIS_DB, UserStates, City, SearchType, \
    DB_NAME, DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT

redis = StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
db = peewee.PostgresqlDatabase(
    DB_NAME,
    user=DB_USERNAME,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
)


class User:
    states = UserStates.as_list()

    transitions = [
        {
            'trigger': 'to_start',
            'source': '*',
            'dest': UserStates.SELECT_TYPE.value,
        },
        {
            'trigger': 'to_select_hotel',
            'source': UserStates.SELECT_TYPE.value,
            'dest': UserStates.SELECT_HOTEL.value,
        },
        {
            'trigger': 'to_select_tour_place',
            'source': UserStates.SELECT_TYPE.value,
            'dest': UserStates.SELECT_TOUR_PLACE.value,
        },
        {
            'trigger': 'to_select_place_from',
            'source': [
                UserStates.SELECT_HOTEL.value,
                UserStates.SELECT_TOUR_PLACE.value,
            ],
            'dest': UserStates.SELECT_PLACE_FROM.value,
        },
        {
            'trigger': 'to_select_date_from',
            'source': UserStates.SELECT_PLACE_FROM.value,
            'dest': UserStates.SELECT_DATE_FROM.value,
        },
        {
            'trigger': 'to_select_date_to',
            'source': UserStates.SELECT_DATE_FROM.value,
            'dest': UserStates.SELECT_DATE_TO.value,
        },
        {
            'trigger': 'to_search_success',
            'source': UserStates.SELECT_DATE_TO.value,
            'dest': UserStates.SEARCH_SUCCESS.value,
        },
        {
            'trigger': 'to_search_fail',
            'source': UserStates.SELECT_DATE_TO.value,
            'dest': UserStates.SEARCH_FAIL.value,
        },
    ]

    def __init__(self, user_id):
        self.user_id = user_id
        self.machine = Machine(
            model=self,
            states=User.states,
            initial=UserStates.SELECT_TYPE.value,
            transitions=User.transitions
        )

        self.type = None
        self.place_from = None
        self.place_to = None
        self.date_from = None
        self.date_to = None

        self.load()

    def __gen_key(self, postfix: str):
        return '{}_{}'.format(self.user_id, postfix)

    @staticmethod
    def __set_to_redis(key, value):
        if value is not None:
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
        state = self.__get_from_redis(self.__gen_key('state'))
        if state is not None:
            self.machine.set_state(state.decode())

        t = self.__get_from_redis(self.__gen_key('type'))
        if t is not None:
            self.type = t.decode()

        place_from = self.__get_from_redis(self.__gen_key('place_from'))
        if place_from is not None:
            self.place_from = int(place_from)

        place_to = self.__get_from_redis(self.__gen_key('place_to'))
        if place_from is not None:
            self.place_to = int(place_to)

        date_from = self.__get_from_redis(self.__gen_key('date_from'))
        if date_from is not None:
            self.date_from = datetime.datetime.strptime(
                date_from.decode(),
                OZON_DATE_FORMAT,
            ).date()

        date_to = self.__get_from_redis(self.__gen_key('date_to'))
        if date_to is not None:
            self.date_to = datetime.datetime.strptime(
                date_to.decode(),
                OZON_DATE_FORMAT,
            ).date()

    def clear(self):
        keys = [
            self.__gen_key(k)
            for k in ['state', 'type', 'place_from',
                      'place_to', 'date_from', 'date_to']
        ]
        redis.delete(*keys)

    @property
    def is_search_by_hotel(self):
        return self.type == SearchType.HOTEL.value

    @property
    def is_search_by_city(self):
        return self.type == SearchType.CITY.value


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
                return requests.request(
                    auth=HTTPBasicAuth(OZON_USERNAME, OZON_PASSWORD),
                    **kwargs
                ).json(strict=False)
            except Exception as e:
                raise e

    def cities_from(self):
        return self.__get(url=OZON_STATIC_URL + 'departures.json')

    def list_city_names_from(self):
        return [
            City(city['name_ru'], city['id'])
            for city in self.cities_from()
        ]

    def meal_types(self):
        return self.__get(url=OZON_STATIC_URL + 'MealTypes.json')

    def hotel_list(self):
        return self.__get(url=OZON_STATIC_URL + 'HotelList.json')

    def cities_to(self):
        return self.__get(url=OZON_STATIC_URL + 'Destinations.json')

    def list_city_names_to(self):
        return [
            City(city['name_ru'], city['id'])
            for country in self.cities_to()
            for city in country['resort']
        ]

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

api = OzonApi()


def search_in_list(query: str, data: list):
    return [x for x in data if query.lower() in x.name.lower()]


class BaseModel(peewee.Model):
    class Meta:
        database = db


class BotUser(BaseModel):
    uid = peewee.CharField()


class Channel(BaseModel):
    user = peewee.ForeignKeyField(BotUser, backref='channels')
    uid = peewee.CharField()
