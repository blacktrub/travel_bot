import datetime

import requests

from .constants import OZON_PARTNER_ID, OZON_API_URL, \
    OZON_DATE_FORMAT, OZON_STATIC_URL


class OzonApi:
    def __init__(self):
        pass

    def __post(self, url: str, body: dict=None):
        return self.__request(
            method='post',
            url=url,
            json=body,
        )

    def __get(self, url: str, query: dict=None):
        return self.__request(
            method='get',
            url=url,
            params=query,
        )

    @staticmethod
    def __request(attempts: int=3, **kwargs):
        for _ in range(attempts):
            try:
                return requests.request(**kwargs, timeout=30).json()
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
