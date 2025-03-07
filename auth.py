# resources/auth.py
from flask_restful import Resource, reqparse
from models import db, User, Subscription, CustomSubscription
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from services.external_api import get_current_weather, evaluate_normal_alert, evaluate_custom_alert

class UserRegistration(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, help="Username is required")
        parser.add_argument('password', type=str, required=True, help="Password is required")
        args = parser.parse_args()

        if User.query.filter_by(username=args['username']).first():
            return {"status": "error", "message": "Username already exists."}, 400

        user = User(username=args['username'])
        user.set_password(args['password'])
        db.session.add(user)
        db.session.commit()
        return {"status": "success", "message": "User registered successfully."}, 201


class UserLogin(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('username', type=str, required=True, help="Username is required")
        parser.add_argument('password', type=str, required=True, help="Password is required")
        args = parser.parse_args()

        user = User.query.filter_by(username=args['username']).first()
        if user and user.check_password(args['password']):
            access_token = create_access_token(identity=user.username)
            alerts = []

            # Evaluate normal subscriptions.
            normal_subs = Subscription.query.filter_by(user_id=user.username).all()
            for sub in normal_subs:
                weather = get_current_weather(sub.location)
                alert_msg = evaluate_normal_alert(sub, weather)
                if alert_msg:
                    alerts.append(alert_msg)

            # Evaluate custom subscriptions.
            custom_subs = CustomSubscription.query.filter_by(user_id=user.username).all()
            for sub in custom_subs:
                weather = get_current_weather(sub.location)
                alert_msg = evaluate_custom_alert(sub, weather)
                if alert_msg:
                    alerts.append(alert_msg)

            # Remove duplicate alerts.
            alerts = list(set(alerts))
            return {"status": "success", "access_token": access_token, "alerts": alerts}, 200

        return {"status": "error", "message": "Invalid credentials."}, 401

class ProtectedResource(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        return {"status": "success", "message": f"Hello, {current_user}!"}, 200
