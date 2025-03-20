# resources/personalization.py
from flask_restful import Resource, reqparse
from flask import request
from marshmallow import ValidationError
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.external_api import (
    save_user_preferences,
    get_suggested_activities,
    get_weather_recommendation,
    get_prediction_confidence,
    update_user_location,
    get_user_preferences,
    get_default_location
)

from flask_restful import Resource
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.external_api import save_user_preferences

class UserPreferences(Resource):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        return {"status": "success", "data": get_user_preferences(user_id)}, 200

    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('preferences', type=dict, required=True, help="Preferences are required")
        args = parser.parse_args()
        message = save_user_preferences(user_id, args['preferences'])
        return {"status": "success", "message": message}, 201


class SuggestedActivities(Resource):
    @jwt_required()  # NEW
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()  # NEW
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_suggested_activities(location)
        return {"status": "success", "data": data}, 200

class WeatherRecommendation(Resource):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        data = get_weather_recommendation(user_id)
        return {"status": "success", "data": data}, 200


class PredictionConfidence(Resource):
    @jwt_required()  # NEW
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()  # NEW
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_prediction_confidence(location)
        return {"status": "success", "data": data}, 200

class UpdateLocation(Resource):
    @jwt_required()
    def put(self):
        user_id = get_jwt_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="New location is required")
        args = parser.parse_args()
        result = update_user_location(user_id, args['location'])
        return {"status": "success", "message": result}, 200
