import datetime

import telebot
from telebot import types

from bot.constants import TOKEN, POOLING_TIMEOUT, UserStates, USER_DATE_FORMAT
from bot.utils import User, api, search_in_list, BotUser, Channel


bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(message.chat.id, 'Добро пожаловать!')
    BotUser.get_or_create(uid=message.from_user.id)
    u = User(message.from_user.id)
    u.clear()
    select_country_from(message)


@bot.message_handler(commands=['new'])
def new(message):
    u = User(message.from_user.id)
    u.clear()
    select_country_from(message)


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
    except (KeyError, IndexError):
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
            'Не верный формат команды, пример: /delete_channel @your_channel_name'
        )
    except Channel.DoesNotExist:
        return bot.send_message(
            message.chat.id,
            'Канал не найден',
        )

    channel.delete_instance()


@bot.message_handler(commands=['to_channels'])
def to_my_channels(message):
    db_user = BotUser.get(uid=message.from_user.id)
    state_user = User(message.from_user.id)
    if message.reply_to_message is None:
        return bot.send_message(
            message.chat.id,
            'Вы должны сделать reply на сообщение которое хотите отправить',
        )

    if not db_user.channels:
        return bot.send_message(
            message.chat.id,
            'Список ваших каналов пуст, вы можете добавить канал '
            'с помощью команды /add_channel @your_channel_name',
        )

    ticket = state_user.ticket
    if ticket is None:
        return bot.send_message(
            message.chat.id,
            'У вас нет активного тикета, повторите поиск',
        )

    if message.reply_to_message.message_id != ticket.message_id:
        return bot.send_message(
            message.chat.id,
            'Сообщение не найдено, повторите поиск',
        )

    ticket = state_user.ticket
    for channel in db_user.channels:
        try:
            btn = types.InlineKeyboardMarkup()
            btn.add(types.InlineKeyboardButton('Бронировать', url=ticket.url))
            bot.send_message(
                channel.uid,
                ticket.message(),
                reply_markup=btn,
            )
        except telebot.apihelper.ApiException:
            bot.send_message(
                message.chat.id,
                'Нужно предоставить боту админ права в '
                'канале {}'.format(channel.uid)
            )


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_COUNTRY_FROM.value)
def select_country_from(message):
    if message.text in ('/new', '/start'):
        return bot.send_message(
            message.chat.id,
            'Введите название страны из которой вы отправляетесь'
        )

    u = User(message.from_user.id)
    founded_countries = search_in_list(message.text, api.get_counties())
    if not founded_countries:
        return bot.send_message(
            message.chat.id,
            'Страны с таким названием не найдено, попробуйте еще раз',
        )

    u.country_from = founded_countries[0].id
    u.to_select_place_from()
    u.flush()
    bot.send_message(
        message.chat.id,
        'Введите название города отправления',
    )


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_PLACE_FROM.value)
def select_place_from(message):
    u = User(message.from_user.id)
    founded_cities = search_in_list(message.text, api.get_cities())
    if not founded_cities:
        return bot.send_message(
            message.chat.id,
            'Города с таким названием не найдено, попробуйте еще раз',
        )

    u.place_from = founded_cities[0].id
    u.to_select_place_to()
    u.flush()
    bot.send_message(
        message.chat.id,
        'Введите название города прибытия',
    )


@bot.message_handler(func=lambda m: User(m.from_user.id).state == UserStates.SELECT_PLACE_TO.value)
def select_place_to(message):
    u = User(message.from_user.id)
    founded_cities = search_in_list(message.text, api.get_cities())
    if not founded_cities:
        return bot.send_message(
            message.chat.id,
            'Города с таким названием не найдено, попробуйте еще раз'
        )

    u.place_to = founded_cities[0].id
    u.to_select_date_from()
    u.flush()
    bot.send_message(
        message.chat.id,
        'Введите дату вылета в формате DD.MM.YYYY'
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
        'Введите дату окончания вашей поездки в формате DD.MM.YYYY',
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

    ticket = api.search(u)
    if ticket:
        u.ticket = ticket
        u.to_search_success()
        bot.send_message(
            message.chat.id,
            'По вашему запросу найден следующий рейс',
        )

        btn = types.InlineKeyboardMarkup()
        btn.add(types.InlineKeyboardButton('Бронировать', url=ticket.url))
        msg = bot.send_message(
            message.chat.id,
            ticket.message(),
            reply_markup=btn,
            disable_notification=True,
        )
        u.ticket.message_id = msg.message_id
    else:
        u.to_search_fail()
        bot.send_message(
            message.chat.id,
            'К сожалению по вашему запросу ничего не найдено',
        )

    bot_user = BotUser.get(uid=message.from_user.id)
    if bot_user.channels and ticket:
        bot.send_message(
            message.chat.id,
            'Для отправки сообщения в ваши каналы, '
            'выберите сообщение и введите команду /to_channels',
        )
    after_search(message)


@bot.message_handler(func=lambda m: User(m.from_user.id).state in [UserStates.SEARCH_FAIL.value, UserStates.SEARCH_SUCCESS.value])
def after_search(message):
    bot.send_message(
        message.chat.id,
        'Для перехода в начало поиска используйте комнаду /new',
    )


bot.polling(none_stop=True)
