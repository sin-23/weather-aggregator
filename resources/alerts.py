# resources/alerts.py
from flask_restful import Resource, reqparse
from services.external_api import get_weather_alerts, subscribe_to_alert, cancel_alert, create_custom_alert, get_default_location
from flask_jwt_extended import jwt_required, get_jwt_identity


class WeatherAlerts(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        # Location is now optional.
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_weather_alerts(location)
        return {"status": "success", "data": data}, 200

class SubscribeAlert(Resource):
    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()  # Get the ID of the logged-in user
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('alert_type', type=str, required=True, help="Alert type is required")
        args = parser.parse_args()
        result = subscribe_to_alert(user_id, args['location'], args['alert_type'])
        return {"status": "success", "message": result}, 201

class CancelAlert(Resource):
    @jwt_required()
    def delete(self):
        user_id = get_jwt_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('alert_type', type=str, required=True, help="Alert type is required")
        args = parser.parse_args()
        result = cancel_alert(user_id, args['location'], args['alert_type'])
        return {"status": "success", "message": result}, 200

class CustomAlert(Resource):
    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('condition', type=str, required=True, help="Custom condition is required")
        args = parser.parse_args()
        result = create_custom_alert(user_id, args['location'], args['condition'])
        return {"status": "success", "message": result}, 201