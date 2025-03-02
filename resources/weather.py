# resources/weather.py
import time, datetime, json
from flask import jsonify
from flask import Response, stream_with_context
from flask_restful import Resource, reqparse, request
from services.external_api import get_current_weather, get_forecast, get_realtime_weather, get_detailed_forecast, \
    get_forecast_with_date


class CurrentWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_current_weather(args['location'])
        return {"status": "success", "data": data}, 200


class ForecastWithDate(Resource):
    def get(self):
        # First, try to get parameters from the query string.
        location = request.args.get("location")
        start_date = request.args.get("start_date")

        # If missing, try to get them from the JSON body.
        if not location or not start_date:
            json_data = request.get_json(silent=True)
            if json_data:
                location = json_data.get("location")
                start_date = json_data.get("start_date")

        # If still missing, return an error.
        if not location or not start_date:
            return {"error": "Missing required parameters: location and start_date"}, 400

        result = get_forecast_with_date(location, start_date)
        return {"status": "success", "data": result}, 200


class RealTimeWeather(Resource):
    def get(self):
        # Retrieve location from the JSON body (not the query string)
        json_data = request.get_json(silent=True)
        location = json_data.get("location") if json_data else None

        if not location:
            return {"error": "Missing required parameter: location (in JSON body)"}, 400

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
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_forecast(args['location'])
        return {"status": "success", "data": data}, 200


class DetailedForecast(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=True, help="Location is required")
        args = parser.parse_args()
        data = get_detailed_forecast(args['location'])
        return {"status": "success", "data": data}, 200