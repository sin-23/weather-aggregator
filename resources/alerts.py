# resources/alerts.py
from flask_restful import Resource, reqparse
from services.external_api import get_weather_alerts, subscribe_to_alert, cancel_alert, create_custom_alert

class WeatherAlerts(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_weather_alerts(args['location'])
        return {"status": "success", "data": data}, 200

class SubscribeAlert(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('alert_type', type=str, required=True, help="Alert type is required")
        args = parser.parse_args()
        result = subscribe_to_alert(args['location'], args['alert_type'])
        return {"status": "success", "message": result}, 201

class CancelAlert(Resource):
    def delete(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('alert_type', type=str, required=True, help="Alert type is required")
        args = parser.parse_args()
        result = cancel_alert(args['location'], args['alert_type'])
        return {"status": "success", "message": result}, 200

class CustomAlert(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('condition', type=str, required=True, help="Condition is required")
        args = parser.parse_args()
        result = create_custom_alert(args['location'], args['condition'])
        return {"status": "success", "message": result}, 201
