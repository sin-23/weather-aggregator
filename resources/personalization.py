# resources/personalization.py
from flask_restful import Resource, reqparse
from flask import request
from marshmallow import ValidationError
from schemas.preferences_schema import preferences_schema
from services.external_api import (
    save_user_preferences,
    get_suggested_activities,
    get_weather_recommendation,
    get_prediction_confidence,
    update_user_location
)

class UserPreferences(Resource):
    def post(self):
        json_data = request.get_json()
        try:
            data = preferences_schema.load(json_data)
        except ValidationError as err:
            return {"status": "error", "errors": err.messages}, 400
        result = save_user_preferences(data['user_id'], data['preferences'])
        return {"status": "success", "message": result}, 201

class SuggestedActivities(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_suggested_activities(args['location'])
        return {"status": "success", "data": data}, 200

class WeatherRecommendation(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_id', type=str, required=True, help="User ID is required")
        args = parser.parse_args()
        data = get_weather_recommendation(args['user_id'])
        return {"status": "success", "data": data}, 200

class PredictionConfidence(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_prediction_confidence(args['location'])
        return {"status": "success", "data": data}, 200

class UpdateLocation(Resource):
    def put(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_id', type=str, required=True, help="User ID is required")
        parser.add_argument('location', type=str, required=True, help="New location is required")
        args = parser.parse_args()
        result = update_user_location(args['user_id'], args['location'])
        return {"status": "success", "message": result}, 200
