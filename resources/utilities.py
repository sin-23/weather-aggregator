# resources/utilities.py
from flask_restful import Resource, reqparse
from services.external_api import get_historical_weather, submit_feedback
import os

class Config:
    DEBUG = True
    TESTING = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    # You can either store your WeatherAPI key in an environment variable or directly here.
    WEATHERAPI_KEY = os.getenv('WEATHERAPI_KEY', 'your_weatherapi_key_here')
    # If you're still using Open-Meteo for other endpoints, keep its key if needed.
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', 'your_default_key')

class HistoricalWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('date', type=str, required=True, help="Date (YYYY-MM-DD) is required")
        args = parser.parse_args()
        data = get_historical_weather(args['location'], args['date'])
        return {"status": "success", "data": data}, 200

class Feedback(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_id', type=str, required=True, help="User ID is required")
        parser.add_argument('feedback', type=str, required=True, help="Feedback is required")
        args = parser.parse_args()
        result = submit_feedback(args['user_id'], args['feedback'])
        return {"status": "success", "message": result}, 201
