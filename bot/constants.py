import os
import enum
import datetime
import collections

from urllib import parse


USER_DATE_FORMAT = '%d.%m.%Y'
TOKEN = os.environ.get('TOKEN')
POOLING_TIMEOUT = 10000000000000

SKYSCANNER_TOKEN = os.environ.get('SKYSCANNER_TOKEN')
SKYSCANNER_LOCALE = 'ru-RU'
SKYSCANNER_CURRENCY = 'RUB'
SKYSCANNER_API_URL = 'http://partners.api.skyscanner.net/apiservices'
SKYSCANNER_API_VERSION = 'v1.0'
SKYSCANNER_DATE_FORMAT = '%Y-%m-%d'
SKYSCANNER_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

REDIS_URL = os.environ.get('REDIS_URL')

DB_URL = parse.urlparse(os.environ["DATABASE_URL"])

DB_NAME = DB_URL.path[1:]
DB_USERNAME = DB_URL.username
DB_PASSWORD = DB_URL.password
DB_HOST = DB_URL.hostname
DB_PORT = DB_URL.port


class UserStates(enum.Enum):
    SELECT_COUNTRY_FROM = 'select_country_from'
    SELECT_PLACE_FROM = 'select_place_from'
    SELECT_PLACE_TO = 'select_place_to'
    SELECT_DATE_FROM = 'select_date_from'
    SELECT_DATE_TO = 'select_date_to'
    SEARCH_SUCCESS = 'search_success'
    SEARCH_FAIL = 'search_fail'

    @classmethod
    def as_list(cls):
        return [v.value for k, v in cls.__members__.items()]


Country = collections.namedtuple('City', 'name id')
City = collections.namedtuple('City', 'name id')
Flight = collections.namedtuple('Flight', 'place_from place_to price_from '
                                          'date carrier')


class Ticket:
    def __init__(self, data):
        self.data = data
        self.outbound = None
        self.inbound = None
        self.url = None
        self.message_id = None

        self.fill_from_data()

    def get_place(self, place_id: str):
        return [
            p for p in self.data['Places']
            if str(p['PlaceId']) == str(place_id)
        ][0]

    def get_carrier(self, carrier_id: str):
        return [
            c for c in self.data['Carriers']
            if str(c['CarrierId']) == str(carrier_id)
        ][0]

    def fill_from_data(self):
        outbounds = [q for q in self.data['Quotes'] if 'OutboundLeg' in q]
        if outbounds:
            outbound = outbounds[0]
            place_from = self.get_place(outbound['OutboundLeg']['OriginId'])
            place_to = self.get_place(outbound['OutboundLeg']['DestinationId'])
            carrier = self.get_carrier(outbound['OutboundLeg']['CarrierIds'][0])

            self.outbound = Flight(
                place_from['Name'],
                place_to['Name'],
                outbound['MinPrice'],
                datetime.datetime.strptime(
                    outbound['OutboundLeg']['DepartureDate'],
                    SKYSCANNER_DATETIME_FORMAT,
                ).date(),
                carrier['Name'],
            )

        inbounds = [q for q in self.data['Quotes'] if 'InboundLeg' in q]
        if inbounds:
            inbound = inbounds[0]
            place_from = self.get_place(inbound['InboundLeg']['OriginId'])
            place_to = self.get_place(inbound['InboundLeg']['DestinationId'])
            carrier = self.get_carrier(inbound['InboundLeg']['CarrierIds'][0])

            self.inbound = Flight(
                place_from['Name'],
                place_to['Name'],
                inbound['MinPrice'],
                datetime.datetime.strptime(
                    inbound['InboundLeg']['DepartureDate'],
                    SKYSCANNER_DATETIME_FORMAT,
                ).date(),
                carrier['Name'],
            )

    def message(self):
        message = 'Информация о рейсе:\n'
        if self.outbound:
            message += 'Путь туда\n' \
                   'Отправление из: {}\n' \
                   'Прибытие в: {}\n' \
                   'Цена: от {} руб.\n' \
                   'Дата отправления: {}\n' \
                   'Авиокомпания: {}\n'.format(*self.outbound)

        if self.inbound:
            message += 'Путь обратно\n' \
                   'Отправление из: {}\n' \
                   'Прибытие в: {}\n' \
                   'Цена: от {} руб.\n' \
                   'Дата отправления: {}\n' \
                   'Авиокомпания: {}\n'.format(*self.inbound)
        return message
