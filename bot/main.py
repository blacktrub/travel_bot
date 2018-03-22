import telebot

from bot.constants import TOKEN, POOLING_TIMEOUT
from bot.utils import User


bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, 'You are welcome')


@bot.message_handler(func=lambda x: True)
def echo(message):
    u = User(message.from_user.id)
    bot.reply_to(message, 'pong')


bot.polling()
