import os
from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv('BOT_TOKEN')


API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SESSION_FILE = 'user_session.session'
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')


CHANNEL_NAMES = [
    'Торговый канал Олега Артемьева',
]

TELEGRAM_USERNAME = 'anlxck'
TELEGRAM_USER_ID = '1067791786'
MY_TELEGRAM_ID = 1067791786
BOT_CHAT_ID = None
TESTNET = False