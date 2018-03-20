import telebot

from .constants import TOKEN, POOLING_TIMEOUT


bot = telebot.TeleBot(TOKEN)


bot.polling(none_stop=True, timeout=POOLING_TIMEOUT)
