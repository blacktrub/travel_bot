import datetime

import telebot
from telebot import types

from bot.constants import TOKEN, POOLING_TIMEOUT, SearchType, UserStates, \
    USER_DATE_FORMAT
from bot.utils import User, api, search_in_list


bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(message.chat.id, 'Добро пожаловать!')
    select_type(message)


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_TYPE.value)
def select_type(message):
    u = User(message.from_user.id)
    if message.text in [SearchType.CITY.value, SearchType.HOTEL.value]:
        if message.text == SearchType.CITY.value:
            u.to_select_tour_place()
            text = 'Введите название города в который вы хотите поехать:'
        if message.text == SearchType.HOTEL.value:
            u.to_select_tour_place()
            text = 'Введите название отеля в который вы хотите поехать:'

        u.type = message.text
        u.flush()
        return bot.send_message(message.chat.id, text)

    keyboard = types.ReplyKeyboardMarkup(row_width=1)

    city_key = types.KeyboardButton(SearchType.CITY.value)
    hotel_key = types.KeyboardButton(SearchType.HOTEL.value)
    keyboard.row(city_key, hotel_key)
    return bot.send_message(
        message.chat.id,
        'Выберите тип поиска:',
        reply_markup=keyboard,
    )


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_HOTEL.value)
def select_hotel(message):
    pass


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_TOUR_PLACE.value)
def select_tour_place(message):
    u = User(message.from_user.id)
    founded_cities = search_in_list(message.text, api.list_city_names_to())
    if not founded_cities:
        return bot.send_message(
            message.chat.id,
            'Города с таким названием не найдено, попробуйте еще раз'
        )

    u.place_to = founded_cities[0].id
    u.to_select_place_from()
    u.flush()
    bot.send_message(
        message.chat.id,
        'Введите название города из которого вы хотите поехать:'
    )


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_PLACE_FROM.value)
def select_tour_from(message):
    u = User(message.from_user.id)
    founded_cities = search_in_list(message.text, api.list_city_names_from())
    if not founded_cities:
        return bot.send_message(
            message.chat.id,
            'Города с таким названием не найдено, попробуйте еще раз'
        )

    u.place_from = founded_cities[0].id
    u.to_select_date_from()
    u.flush()
    bot.send_message(
        message.chat.id,
        'Введите дату отезда в формате DD.MM.YYYY:'
    )


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_DATE_FROM.value)
def select_date_from(message):
    u = User(message.from_user.id)
    try:
        date = datetime.datetime.strptime(message.text, USER_DATE_FORMAT).date()
    except ValueError:
        return bot.send_message(
            message.chat.id,
            'Не верный формат даты, попробуйте еще раз'
        )

    u.date_from = date
    u.to_select_date_to()
    u.flush()
    bot.send_message(
        message.chat.id,
        'Введите дату окончания вашей поездки в формате DD.MM.YYYY:',
    )


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_DATE_TO.value)
def select_date_to(message):
    u = User(message.from_user.id)
    try:
        date = datetime.datetime.strptime(message.text, USER_DATE_FORMAT).date()
    except ValueError:
        return bot.send_message(
            message.chat.id,
            'Не верный формат даты, попробуйте еще раз'
        )

    if date < u.date_from:
        return bot.send_message(
            message.chat.id,
            'Дата окончания поездки должна быть больше даты начала поездки',
        )

    u.date_to = date
    u.flush()
    bot.send_message(
        message.chat.id,
        'success',
    )

    tours = []
    if u.is_search_by_city:
        tours = api.search_by_place(
            u.place_from,
            u.place_to,
            u.date_from,
            u.date_to,
        )
    elif u.is_search_by_hotel:
        tours = api.search_by_hotel(
            u.place_from,
            u.place_to,
            u.date_from,
            u.date_to,
        )

    if tours:
        u.to_search_success()
        bot.send_message(
            message.chat.id,
            'По вашему запросу найдены следующие туры:',
        )
    else:
        u.to_search_fail()
        bot.send_message(
            message.chat.id,
            'К сожалению по вашему запросу ничего не найдено',
        )


bot.polling()
