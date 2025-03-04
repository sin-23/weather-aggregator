# resources/comparisons.py
from flask_restful import Resource, reqparse
from services.external_api import compare_weather, get_climate_data, get_trending_weather, get_seasonal_changes
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.external_api import get_default_location  # NEW

def split_locations(value):
    """
    Splits the input string on commas and returns a list of trimmed location names.
    For example, "London, Paris, Tokyo" becomes ["London", "Paris", "Tokyo"].
    """
    return [loc.strip() for loc in value.split(',') if loc.strip()]

class CompareWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        # Use the custom split_locations function as the type
        parser.add_argument('locations', type=split_locations, required=True,
                            help="Provide a comma-separated list of locations")
        args = parser.parse_args()
        data = compare_weather(args['locations'])
        return {"status": "success", "data": data}, 200


class ClimateData(Resource):
    @jwt_required()  # NEW
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('region', type=str, required=False, help="Region is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()  # NEW
        region = get_default_location(user_id, args.get("region"))
        if not region:
            return {"error": "No region provided and no preferences found. Please update your location."}, 400

        data = get_climate_data(region)
        return {"status": "success", "data": data}, 200

class TrendingWeather(Resource):
    def get(self):
        data = get_trending_weather()
        return {"status": "success", "data": data}, 200


class SeasonalChanges(Resource):
    @jwt_required()  # NEW
    def get(self):
        parser = reqparse.RequestParser()
        # Change required to optional
        parser.add_argument('region', type=str, required=False, help="Region is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()  # NEW
        region = get_default_location(user_id, args.get("region"))
        if not region:
            return {"error": "No region provided and no preferences found. Please update your location."}, 400

        data = get_seasonal_changes(region)
        return {"status": "success", "data": data}, 200