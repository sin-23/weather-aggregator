# resources/weather.py
from flask_restful import Resource, reqparse
from services.external_api import get_current_weather, get_forecast, get_realtime_weather, get_next_7_days_forecast

class CurrentWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_current_weather(args['location'])
        return {"status": "success", "data": data}, 200

class WeatherForecast(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('start_date', type=str, required=False, help="Start date in YYYY-MM-DD format (optional)")
        args = parser.parse_args()
        data = get_forecast(args['location'], args.get('start_date'))
        return {"status": "success", "data": data}, 200

class RealTimeWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_realtime_weather(args['location'])
        return {"status": "success", "data": data}, 200

class Next7DaysForecast(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_forecast(args['location'])
        return {"status": "success", "data": data}, 200

