# resources/weather.py
import time, datetime, json
from flask import jsonify
from flask import Response, stream_with_context
from flask_restful import Resource, reqparse, request
from services.external_api import get_current_weather, get_forecast, get_realtime_weather, get_detailed_forecast, \
    get_forecast_with_date, get_default_location
from flask_jwt_extended import jwt_required, get_jwt_identity


class CurrentWeather(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_current_weather(location, user_id)
        return {"status": "success", "data": data}, 200


class ForecastWithDate(Resource):
    @jwt_required()
    def get(self):
        # First, try to get parameters from the query string.
        location = request.args.get("location")
        start_date = request.args.get("start_date")

        # If missing, try to get them from the JSON body.
        if not location or not start_date:
            json_data = request.get_json(silent=True)
            if json_data:
                location = json_data.get("location", location)
                start_date = json_data.get("start_date", start_date)

        # Get the logged-in user ID
        user_id = get_jwt_identity()
        location = get_default_location(user_id, location)  # Use default if not provided

        # If still missing, return an error.
        if not location or not start_date:
            return {"error": "Missing required parameters: location and start_date"}, 400

        result = get_forecast_with_date(location, start_date)
        return {"status": "success", "data": result}, 200


class RealTimeWeather(Resource):
    @jwt_required()
    def get(self):
        # Retrieve location from JSON body if provided
        json_data = request.get_json(silent=True)
        location = json_data.get("location") if json_data else None

        # Get the logged-in user ID
        user_id = get_jwt_identity()
        location = get_default_location(user_id, location)  # Use default if not provided

        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        @stream_with_context
        def event_stream():
            while True:
                current_data = get_current_weather(location)
                # Append the current update time (including seconds)
                current_data["update_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                yield f"data: {json.dumps({'status': 'success', 'data': current_data})}\n\n"
                time.sleep(5)

        return Response(event_stream(), mimetype="text/event-stream")

class Next7DaysForecast(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_forecast(location)
        return {"status": "success", "data": data}, 200


class DetailedForecast(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_detailed_forecast(args['location'])
        return {"status": "success", "data": data}, 200