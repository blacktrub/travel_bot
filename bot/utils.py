import datetime

import requests
from transitions import Machine
from redis import StrictRedis
import peewee

from .constants import REDIS_URL, UserStates, City, Country, Ticket, DB_NAME, \
    DB_USERNAME, DB_PASSWORD, DB_HOST, DB_PORT, SKYSCANNER_TOKEN, \
    SKYSCANNER_API_URL, SKYSCANNER_API_VERSION, SKYSCANNER_CURRENCY, \
    SKYSCANNER_LOCALE, SKYSCANNER_DATE_FORMAT

from .errors import SkyscannerApiNotFound


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
            'dest': UserStates.SELECT_COUNTRY_FROM.value,
        },
        {
            'trigger': 'to_select_place_from',
            'source': UserStates.SELECT_COUNTRY_FROM.value,
            'dest': UserStates.SELECT_PLACE_FROM.value,
        },
        {
            'trigger': 'to_select_place_to',
            'source': UserStates.SELECT_PLACE_FROM.value,
            'dest': UserStates.SELECT_PLACE_TO.value,
        },
        {
            'trigger': 'to_select_date_from',
            'source': UserStates.SELECT_PLACE_TO.value,
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
            initial=UserStates.SELECT_COUNTRY_FROM.value,
            transitions=User.transitions
        )

        self.country_from = None
        self.place_from = None
        self.place_to = None
        self.date_from = None
        self.date_to = None
        self.ticket = None

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
        d0 = self.date_from.strftime(SKYSCANNER_DATE_FORMAT) if self.date_from else None
        d1 = self.date_to.strftime(SKYSCANNER_DATE_FORMAT) if self.date_to else None
        self.__set_to_redis(self.__gen_key('state'), self.state)
        self.__set_to_redis(self.__gen_key('country_from'), self.country_from)
        self.__set_to_redis(self.__gen_key('place_from'), self.place_from)
        self.__set_to_redis(self.__gen_key('place_to'), self.place_to)
        self.__set_to_redis(self.__gen_key('date_from'), d0)
        self.__set_to_redis(self.__gen_key('date_to'), d1)

    def load(self):
        state = self.__get_from_redis(self.__gen_key('state'))
        if state is not None:
            self.machine.set_state(state.decode())

        country_from = self.__get_from_redis(self.__gen_key('country_from'))
        if country_from is not None:
            self.country_from = country_from.decode()

        place_from = self.__get_from_redis(self.__gen_key('place_from'))
        if place_from is not None:
            self.place_from = place_from.decode()

        place_to = self.__get_from_redis(self.__gen_key('place_to'))
        if place_to is not None:
            self.place_to = place_to.decode()

        date_from = self.__get_from_redis(self.__gen_key('date_from'))
        if date_from is not None:
            self.date_from = datetime.datetime.strptime(
                date_from.decode(),
                SKYSCANNER_DATE_FORMAT,
            ).date()

        date_to = self.__get_from_redis(self.__gen_key('date_to'))
        if date_to is not None:
            self.date_to = datetime.datetime.strptime(
                date_to.decode(),
                SKYSCANNER_DATE_FORMAT,
            ).date()

    def clear(self):
        keys = [
            self.__gen_key(k)
            for k in ['state', 'place_from', 'place_to',
                      'date_from', 'date_to']
        ]
        redis.delete(*keys)
        self.machine.set_state(UserStates.SELECT_COUNTRY_FROM.value)
        self.country_from = None
        self.place_from = None
        self.place_to = None
        self.date_from = None
        self.date_to = None


class SkyscannerApi:
    def __init__(self, token: str=SKYSCANNER_TOKEN):
        self.token = token
        # When you need to make a client-side call please insure that you use
        # your short API key (the first 16 characters of you key).
        self.short_token = self.token[:16]

    def request(self,
                url: str,
                params: dict=None,
                timeout: int=10,
                attempts: int=3):
        if params is None:
            params = {}

        params.update({'apikey': self.token})
        headers = {
            'Accept': 'application/json',
        }
        for _ in range(attempts):
            try:
                return requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=timeout,
                ).json()
            except Exception as e:
                raise e

    def get_all_geo(self):
        url = '{}/{}/{}'.format(
            SKYSCANNER_API_URL,
            'geo',
            SKYSCANNER_API_VERSION,
        )
        return self.request(url, params={'languageid': SKYSCANNER_LOCALE})

    def get_counties(self):
        data = self.get_all_geo()
        return (
            Country(country['Name'], country['Id'])
            for continents in data['Continents']
            for country in continents['Countries']
        )

    def get_cities(self):
        data = self.get_all_geo()
        return (
            City(city['Name'], city['Id'])
            for continent in data['Continents']
            for country in continent['Countries']
            for city in country['Cities']
        )

    def make_booking_url(self, u: User):
        return '{}/{}/{}/{}/{}/{}/{}/{}/{}/{}?apiKey={}'.format(
            SKYSCANNER_API_URL,
            'referral',
            SKYSCANNER_API_VERSION,
            u.country_from,
            SKYSCANNER_CURRENCY,
            SKYSCANNER_LOCALE,
            u.place_from,
            u.place_to,
            u.date_from.strftime(SKYSCANNER_DATE_FORMAT),
            u.date_to.strftime(SKYSCANNER_DATE_FORMAT),
            self.short_token,
        )

    def search(self, u: User, attempts: int=3):
        data = None
        for _ in range(attempts):
            try:
                url = '{}/{}/{}/{}/{}/{}/{}/{}/{}/{}'.format(
                    SKYSCANNER_API_URL,
                    'browsequotes',
                    SKYSCANNER_API_VERSION,
                    u.country_from,
                    SKYSCANNER_CURRENCY,
                    SKYSCANNER_LOCALE,
                    u.place_from,
                    u.place_to,
                    u.date_from.strftime(SKYSCANNER_DATE_FORMAT),
                    u.date_to.strftime(SKYSCANNER_DATE_FORMAT),
                )
                data = self.request(url)
                if data.get('Quotes', None) is None:
                    raise SkyscannerApiNotFound
                else:
                    break

            except SkyscannerApiNotFound:
                u.date_from = u.date_from - datetime.timedelta(days=1)
                u.date_to = u.date_to - datetime.timedelta(days=1)
                continue
            except Exception as e:
                raise e

        if data is None or not data.get('Quotes'):
            return

        ticket = Ticket(data)
        ticket.url = self.make_booking_url(u)
        return ticket


api = SkyscannerApi()


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
