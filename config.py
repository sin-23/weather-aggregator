# config.py
import os

class Config:
    DEBUG = True
    TESTING = False
    JWT_SECRET_KEY = '4H5V7JaAokUsuzPq9vZ2-zpuUk98MwvRZE-kjNmEkV'  # Replace with a secure key
    # Use the environment variable if set; otherwise, use the default key.
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', '9ed6e3b6b2cc9ceca7298c7319ea1fb0')
