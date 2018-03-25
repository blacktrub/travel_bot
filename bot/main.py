import datetime

import telebot
from telebot import types

from bot.constants import TOKEN, POOLING_TIMEOUT, SearchType, UserStates, \
    USER_DATE_FORMAT
from bot.utils import User, api, search_in_list, BotUser, Channel


bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(message.chat.id, 'Добро пожаловать!')
    BotUser.get_or_create(uid=message.from_user.id)
    select_type(message)


@bot.message_handler(commands=['new'])
def new(message):
    u = User(message.from_user.id)
    u.clear()
    select_type(message)


@bot.message_handler(commands=['list_channels'])
def list_channels(message):
    u = BotUser.get(uid=message.from_user.id)
    if not u.channels:
        msg = 'Список ваших каналов пуст, вы можете добавить канал ' \
              'с помощью команды /add_channel @your_channel_name'
    else:
        msg = 'Список ваших каналов:\n' + \
              '\n'.join([c.uid for c in u.channels])

    bot.send_message(message.chat.id, msg)


@bot.message_handler(commands=['add_channel'])
def add_channel(message):
    u = BotUser.get(uid=message.from_user.id)

    try:
        channel_name = message.text.strip().split()[1]
        if '@' not in channel_name:
            channel_name = '@' + channel_name

        bot.get_chat(channel_name)
    except telebot.apihelper.ApiException:
        return bot.send_message(
            message.chat.id,
            'Произошла ошибка при добавлении канала, возможно вы пытаетесь '
            'добавить не существующий или приватный канал',
        )
    except KeyError:
        return bot.send_message(
            message.chat.id,
            'Не верный формат комнады, пример: /add_channel @your_channel_name'
        )

    bot.send_message(
        message.chat.id,
        'Вы успешно добавили канал, для репоста в ваш канал вам '
        'необходимо дать админ права данному боту в настройках канала',
    )
    Channel.get_or_create(user=u, uid=channel_name)


@bot.message_handler(commands=['delete_channel'])
def delete_channel(message):
    u = BotUser.get(uid=message.from_user.id)

    try:
        channel_name = message.text.strip().split()[1]
        channel = Channel.get(user=u, uid=channel_name)
    except KeyError:
        return bot.send_message(
            message.chat.id,
            'Не верный формат комнады, пример: /delete_channel @your_channel_name'
        )
    except Channel.DoesNotExist:
        return bot.send_message(
            message.chat.id,
            'Канал не найден',
        )

    channel.delete_instance()


@bot.message_handler(commands=['to_channels'])
def to_my_channels(message):
    u = BotUser.get(uid=message.from_user.id)
    if message.reply_to_message is None:
        return bot.send_message(
            message.chat.id,
            'Вы должны сделать reply на сообщение которое хотите отправить',
        )

    if not u.channels:
        return bot.send_message(
            message.chat.id,
            'Список ваших каналов пуст, вы можете добавить канал '
            'с помощью команды /add_channel @your_channel_name',
        )

    for channel in u.channels:
        try:
            bot.forward_message(
                channel.uid,
                message.chat.id,
                message.reply_to_message.message_id,
            )
        except telebot.apihelper.ApiException:
            bot.send_message(
                message.chat.id,
                'Нужно предоставить боту админ права в '
                'канале {}'.format(channel.uid)
            )


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
