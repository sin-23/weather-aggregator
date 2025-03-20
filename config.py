import os

class Config:
    DEBUG = True
    TESTING = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', '4H5V7JaAokUsuzPq9vZ2-zpuUk98MwvRZE-kjNmEkV')
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '9ed6e3b6b2cc9ceca7298c7319ea1fb0')
    WEATHERAPI_KEY = os.getenv('WEATHERAPI_KEY', '15b6b2ba19994d6bbd785802252003')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///weather_aggregator.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False