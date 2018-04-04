import os
import json
import datetime

import requests
from transitions import Machine
from redis import StrictRedis
import peewee

from .constants import OZON_PARTNER_ID, OZON_API_URL, \
    OZON_DATE_FORMAT, OZON_STATIC_URL, OZON_AUTH, \
    REDIS_URL, UserStates, City, Hotel, SearchType, \
    DB_NAME, DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT, Tour, \
    OZON_DATETIME_FORMAT, USER_DATE_FORMAT, MAX_RESULTS

from .errors import OzonApiNotFound

redis = StrictRedis.from_url(REDIS_URL)
db = peewee.PostgresqlDatabase(
    DB_NAME,
    user=DB_USERNAME,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
)


class SaveInstance(type):
    __instances = {}

    def __call__(cls, *args, **kwargs):
        print()
        if cls not in cls.__instances:
            cls.__instances[cls] = super().__call__(*args, **kwargs)
        return cls.__instances[cls]


class User(metaclass=SaveInstance):
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
        self.hotel = None
        self.place_to = None
        self.date_from = None
        self.date_to = None
        self.tours = None

        self.load()

    @property
    def place_to_id(self):
        return self.place_to or self.hotel

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
        self.__set_to_redis(self.__gen_key('hotel'), self.hotel)
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

        hotel = self.__get_from_redis(self.__gen_key('hotel'))
        if hotel is not None:
            self.hotel = int(hotel)

        place_to = self.__get_from_redis(self.__gen_key('place_to'))
        if place_to is not None:
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
        self.machine.set_state(UserStates.SELECT_TYPE.value)
        self.type = None
        self.place_from = None
        self.place_to = None
        self.date_from = None
        self.date_to = None

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
        headers = {'Authorization': OZON_AUTH}
        kwargs.update({'headers': headers})

        for _ in range(attempts):
            try:
                return requests.request(**kwargs).json(strict=False)
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
        # we take info about the hotels from file
        # because a json data from api contains syntax errors
        hotel_file = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            'hotels',
        )
        with open(hotel_file, encoding='utf-8') as f:
            return [
                Hotel(h['name'], h['id'])
                for h in json.loads(f.readline())
            ]

    def hotel_name_from_id(self, hotel_id: int):
        hotel_list = self.hotel_list()
        return [h for h in hotel_list if int(h.id) == int(hotel_id)][0]

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
                        place_to_id: int,
                        date_from: datetime.date,
                        date_to: datetime.date,
                        adults: int=1,
                        dynamic_search: bool = False,
                        meta_search: bool = False):
        body = {
            'DepartureCityId': place_from_id,
            'HotelId': place_to_id,
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
                        meta_search: bool = False):
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

    def search(self, u: User, attempts: int=3):
        method = None
        if u.is_search_by_city:
            method = api.search_by_place
        elif u.is_search_by_hotel:
            method = api.search_by_hotel

        params = {
            'place_from_id': u.place_from,
            'place_to_id': u.place_to_id,
            'date_from': u.date_from,
            'date_to': u.date_to,
        }
        results = []
        for _ in range(attempts):
            try:
                data = method(**params)
                status = data.get('StatusCode', None)
                if status is not None and status == 200:
                    response_results = data.get('Result', None)
                    if response_results is not None:
                        results = response_results
                        if not isinstance(results, list):
                            results = [results]
                        break
                    else:
                        raise OzonApiNotFound
            except OzonApiNotFound:
                params['date_from'] = params['date_from'] \
                                      - datetime.timedelta(days=1)
                params['date_to'] = params['date_to'] \
                                    - datetime.timedelta(days=1)
            except Exception as e:
                raise e

        tours = []
        for result in results[:MAX_RESULTS]:
            offers = []
            if u.is_search_by_city:
                offers = [min(result.get('HotelOffers', []),
                             key=lambda x: x['PriceRur'])]
            elif u.is_search_by_hotel:
                offers = result.get('Offers', [])

            for offer in offers:
                tours.append(Tour(
                    name=self.hotel_name_from_id(result['HotelId']).name,
                    id=result['HotelId'],
                    url=result['OffersUrl'],
                    date_from=datetime.datetime.strptime(
                        offer['DateFrom'],
                        OZON_DATETIME_FORMAT,
                    ).strftime(USER_DATE_FORMAT),
                    days=offer['DaysDuration'],
                    price=offer['PriceRur'],
                ))

        return tours


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
