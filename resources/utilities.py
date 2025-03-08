# resources/utilities.py
from flask_restful import Resource, reqparse
from services.external_api import get_historical_weather, submit_feedback
import os
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.external_api import get_default_location
from models import Feedback, db
from sqlalchemy import func


class Config:
    DEBUG = True
    TESTING = False
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    # You can either store your WeatherAPI key in an environment variable or directly here.
    WEATHERAPI_KEY = os.getenv('WEATHERAPI_KEY', 'your_weatherapi_key_here')
    # If you're still using Open-Meteo for other endpoints, keep its key if needed.
    OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY', 'your_default_key')


class HistoricalWeather(Resource):
    @jwt_required()  # NEW
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        parser.add_argument('date', type=str, required=True, help="Date (YYYY-MM-DD) is required")
        args = parser.parse_args()

        user_id = get_jwt_identity()  # NEW
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_historical_weather(location, args['date'])
        return {"status": "success", "data": data}, 200

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

