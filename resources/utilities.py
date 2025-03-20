# from models import Feedback, db
# from sqlalchemy import func
# #
# #
# # class Config:
# #     DEBUG = True
# #     TESTING = False
# #     JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
# #     # You can either store your WeatherAPI key in an environment variable or directly here.
# #     WEATHERAPI_KEY = os.getenv('WEATHERAPI_KEY', 'your_weatherapi_key_here')
# #     # If you're still using Open-Meteo for other endpoints, keep its key if needed.
# #     OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', 'your_default_key')
#
# # resources/personalization.py
# from flask_restful import Resource, reqparse
# from flask import request
# from marshmallow import ValidationError
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from services.external_api import (
#     save_user_preferences,
#     get_suggested_activities,
#     get_weather_recommendation,
#     get_prediction_confidence,
#     update_user_location,
#     get_user_preferences,
#     get_default_location
# )
#
# from flask_restful import Resource
# from flask import request
# from flask_jwt_extended import jwt_required, get_jwt_identity
# from services.external_api import save_user_preferences

from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from models import db, Feedback
from services.user_functions import get_user_preferences, update_user_location, save_user_preferences, submit_feedback

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

class UpdateLocation(Resource):
    @jwt_required()
    def put(self):
        user_id = get_jwt_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="New location is required")
        args = parser.parse_args()
        result = update_user_location(user_id, args['location'])
        return {"status": "success", "message": result}, 200


class FeedbackResource(Resource):
   @jwt_required()
   def post(self):
       parser = reqparse.RequestParser()
       parser.add_argument('rating', type=str, required=True, help="Rating is required")
       parser.add_argument('comment', type=str, required=False)
       args = parser.parse_args()
       user_id = get_jwt_identity()
       success, message = submit_feedback(user_id, args['rating'], args.get('comment', ""))
       if success:
           return {"status": "success", "message": message}, 201
       else:
           return {"status": "error", "message": message}, 400


class AverageRatingResource(Resource):
   def get(self):
       # Aggregate average rating and count.
       result = db.session.query(
           func.avg(Feedback.rating).label("average"),
           func.count(Feedback.id).label("count")
       ).one()
       average = result.average
       count = result.count


       # Retrieve all feedback records.
       all_feedbacks = Feedback.query.all()
       feedback_list = []
       for fb in all_feedbacks:
           feedback_list.append({
               "rating": fb.rating,
               "comment": fb.comment,
               "created_at": fb.created_at.strftime("%Y-%m-%d %H:%M:%S")
           })


       return {
           "status": "success",
           "average_rating": float(average) if average is not None else None,
           "count": count,
           "feedbacks": feedback_list
       }, 200

