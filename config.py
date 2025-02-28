# config.py
import os

class Config:
    DEBUG = True
    TESTING = False
    JWT_SECRET_KEY = '4H5V7JaAokUsuzPq9vZ2-zpuUk98MwvRZE-kjNmEkV'  # Replace with a secure key
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '9ed6e3b6b2cc9ceca7298c7319ea1fb0')
    WEATHERAPI_KEY = os.getenv('WEATHERAPI_KEY', '3c34352b2bca48778a495626252702')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'mysql+pymysql://admin:qwer1234@localhost/weather1')
    SQLALCHEMY_TRACK_MODIFICATIONS = False