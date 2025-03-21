from flask_restful import Resource, reqparse
from services.alert_functions import get_weather_alerts, subscribe_to_alert, create_custom_alert, cancel_alert
from services.user_functions import get_default_location
from flask_jwt_extended import jwt_required, get_jwt_identity

class WeatherAlerts(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
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
        user_id = get_jwt_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('alert_type', type=str, required=True, help="Alert type is required")
        args = parser.parse_args()
        success, message = subscribe_to_alert(user_id, args['location'], args['alert_type'])
        if not success:
            return {"status": "error", "message": message}, 400
        return {"status": "success", "message": message}, 201

class CancelAlert(Resource):
    @jwt_required()
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("subscription_type", type=str, required=True, help="subscription_type must be 'normal' or 'custom'.")
        parser.add_argument("location", type=str, required=True, help="Location is required.")
        parser.add_argument("alert_type", type=str, required=False, help="For normal alerts, alert_type is required.")
        parser.add_argument("condition", type=str, required=False, help="For custom alerts, condition is required.")
        parser.add_argument("operator", type=str, required=False, help="For custom alerts, operator is required for temperature and wind_speed alerts.")
        parser.add_argument("threshold", type=str, required=False, help="Threshold is required for the selected alert type.")
        args = parser.parse_args()

        return cancel_alert(args)

class CustomAlert(Resource):
    @jwt_required()
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument("location", type=str, required=True, help="Location cannot be blank.")
        parser.add_argument("condition", type=str, required=True, help="Condition cannot be blank.")
        parser.add_argument("operator", type=str, required=False)
        parser.add_argument("threshold", type=str, required=False)
        args = parser.parse_args()

        user_id = get_jwt_identity()
        if not user_id:
            return {"status": "error", "message": "User not authenticated."}, 401

        success, message = create_custom_alert(
            user_id,
            args["location"],
            args["condition"],
            operator=args.get("operator"),
            threshold=args.get("threshold")
        )
        if not success:
            return {"status": "error", "message": message}, 400
        return {"status": "success", "message": message}, 201