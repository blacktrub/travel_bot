import datetime

import requests
from transitions import Machine

from .constants import OZON_PARTNER_ID, OZON_API_URL, \
    OZON_DATE_FORMAT, OZON_STATIC_URL


class User:
    states = [
        'select_type',
        'select_place_from',
        'select_date_from',
        'select_tour_place',
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
            'trigger': 'to_select_place_from',
            'source': 'select_type',
            'dest': 'select_place_from'
        },
        {
            'trigger': 'to_select_date_from',
            'source': 'select_place_from',
            'dest': 'select_date_from'
        },
        {
            'trigger': 'to_select_tour_place',
            'source': 'select_date_from',
            'dest': 'select_tour_place'
        },
        {
            'trigger': 'to_select_date_to',
            'source': 'select_tour_place',
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
