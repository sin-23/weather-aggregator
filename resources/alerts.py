from flask_restful import Resource, reqparse
from services.alert_functions import get_weather_alerts, subscribe_to_alert, create_custom_alert, CUSTOM_ALERT_TYPE, ALERT_TYPE_TEMP, ALERT_TYPE_WIND, ALERT_TYPE_PRECIP
from services.user_functions import get_default_location
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Subscription, CustomSubscription

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
        # For normal alerts:
        parser.add_argument("alert_type", type=str, required=False, help="For normal alerts, alert_type is required.")
        # For custom alerts:
        parser.add_argument("condition", type=str, required=False, help="For custom alerts, condition is required.")
        parser.add_argument("operator", type=str, required=False, help="For custom alerts, operator is required for temperature and wind_speed alerts.")
        parser.add_argument("threshold", type=str, required=False, help="Threshold is required for the selected alert type.")
        args = parser.parse_args()

        subscription_type = args.get("subscription_type").lower().strip()
        location = args.get("location").strip()
        user_id = get_jwt_identity()

        if subscription_type not in ["normal", "custom"]:
            return {"status": "error", "message": "subscription_type must be 'normal' or 'custom'."}, 400

        if subscription_type == "normal":
            alert_type_str = args.get("alert_type")
            if not alert_type_str:
                return {"status": "error", "message": "For normal subscriptions, 'alert_type' is required."}, 400
            try:
                alert_type_int = int(alert_type_str)
            except ValueError:
                return {"status": "error", "message": "alert_type must be an integer."}, 400

            subscription = Subscription.query.filter_by(
                user_id=user_id,
                location=location,
                alert_type=alert_type_int
            ).first()
            if subscription:
                db.session.delete(subscription)
                db.session.commit()
                return {"status": "success", "message": f"Cancelled normal alert type {alert_type_int} ({CUSTOM_ALERT_TYPE.get(alert_type_int, 'Unknown')}) for {location}."}, 200
            else:
                return {"status": "error", "message": f"No active normal subscription for alert type {alert_type_int} ({CUSTOM_ALERT_TYPE.get(alert_type_int, 'Unknown')}) in {location}."}, 400

        elif subscription_type == "custom":
            condition = args.get("condition")
            if not condition:
                return {"status": "error", "message": "For custom subscriptions, 'condition' is required."}, 400
            cond_lower = condition.lower().strip()
            mapping = {
                "temperature": ALERT_TYPE_TEMP,
                "wind_speed": ALERT_TYPE_WIND,
                "precipitation": ALERT_TYPE_PRECIP
            }
            alert_type = mapping.get(cond_lower)
            if alert_type is None:
                return {"status": "error", "message": "Condition must be 'temperature', 'wind_speed', or 'precipitation'."}, 400

            if alert_type in (ALERT_TYPE_TEMP, ALERT_TYPE_WIND):
                operator = args.get("operator")
                threshold = args.get("threshold")
                if not operator or operator.strip() not in (">", "<"):
                    return {"status": "error", "message": "For custom temperature and wind_speed alerts, 'operator' is required and must be '>' or '<'."}, 400
                operator = operator.strip()
                if not threshold:
                    return {"status": "error", "message": "For custom temperature and wind_speed alerts, 'threshold' is required."}, 400
                try:
                    float(threshold)
                except ValueError:
                    return {"status": "error", "message": "For custom temperature and wind_speed alerts, 'threshold' must be numeric."}, 400
            elif alert_type == ALERT_TYPE_PRECIP:
                threshold = args.get("threshold")
                valid_levels = ["no rain", "light", "moderate", "heavy"]
                if not threshold or threshold.lower().strip() not in valid_levels:
                    return {"status": "error", "message": "For custom precipitation alerts, 'threshold' must be one of: no rain, light, moderate, heavy."}, 400
                operator = None
                threshold = threshold.lower().strip()

            subscription = CustomSubscription.query.filter_by(
                user_id=user_id,
                location=location,
                alert_type=alert_type,
                operator=operator,
                threshold=str(threshold)
            ).first()
            if subscription:
                db.session.delete(subscription)
                db.session.commit()
                return {"status": "success", "message": f"Cancelled custom alert for {CUSTOM_ALERT_TYPE.get(alert_type, 'Unknown')} at {location}."}, 200
            else:
                return {"status": "error", "message": f"No active custom subscription found for {cond_lower} alert at {location}."}, 400

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