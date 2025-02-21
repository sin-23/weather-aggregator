# resources/utilities.py
from flask_restful import Resource, reqparse
from services.external_api import get_historical_weather, submit_feedback

class HistoricalWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        parser.add_argument('date', type=str, required=True, help="Date (YYYY-MM-DD) is required")
        args = parser.parse_args()
        data = get_historical_weather(args['location'], args['date'])
        return {"status": "success", "data": data}, 200

class Feedback(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('user_id', type=str, required=True, help="User ID is required")
        parser.add_argument('feedback', type=str, required=True, help="Feedback is required")
        args = parser.parse_args()
        result = submit_feedback(args['user_id'], args['feedback'])
        return {"status": "success", "message": result}, 201
