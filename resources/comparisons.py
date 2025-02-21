# resources/comparisons.py
from flask_restful import Resource, reqparse
from services.external_api import compare_weather, get_climate_data, get_trending_weather, get_seasonal_changes

class CompareWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('locations', type=str, action='split', required=True,
                            help="Provide a comma-separated list of locations")
        args = parser.parse_args()
        data = compare_weather(args['locations'])
        return {"status": "success", "data": data}, 200

class ClimateData(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('region', type=str, required=True, help="Region is required")
        args = parser.parse_args()
        data = get_climate_data(args['region'])
        return {"status": "success", "data": data}, 200

class TrendingWeather(Resource):
    def get(self):
        data = get_trending_weather()
        return {"status": "success", "data": data}, 200

class SeasonalChanges(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('region', type=str, required=True, help="Region is required")
        args = parser.parse_args()
        data = get_seasonal_changes(args['region'])
        return {"status": "success", "data": data}, 200
