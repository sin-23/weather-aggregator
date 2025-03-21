from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask import request, Response, stream_with_context
import json, time, datetime
from services.weather_functions import get_current_weather, get_forecast_with_date, get_forecast, get_detailed_forecast, compare_weather, get_climate_data, split_locations, get_trending_weather, get_seasonal_changes, get_historical_weather, get_suggested_activities, get_weather_recommendation, get_prediction_confidence
from services.user_functions import get_default_location

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
        location = request.args.get("location")
        start_date = request.args.get("start_date")

        if not location or not start_date:
            json_data = request.get_json(silent=True)
            if json_data:
                location = json_data.get("location", location)
                start_date = json_data.get("start_date", start_date)

        user_id = get_jwt_identity()
        location = get_default_location(user_id, location)

        if not location or not start_date:
            return {"error": "Missing required parameters: location and start_date"}, 400

        result = get_forecast_with_date(location, start_date)
        return {"status": "success", "data": result}, 200

class RealTimeWeather(Resource):
    @jwt_required()
    def get(self):
        json_data = request.get_json(silent=True)
        location = json_data.get("location") if json_data else None

        user_id = get_jwt_identity()
        location = get_default_location(user_id, location)

        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        @stream_with_context
        def event_stream():
            while True:
                current_data = get_current_weather(location)
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
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_detailed_forecast(location)
        return {"status": "success", "data": data}, 200

class CompareWeather(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('locations', type=split_locations, required=True, help="Provide a comma-separated list of locations")
        args = parser.parse_args()
        data = compare_weather(args['locations'])
        return {"status": "success", "data": data}, 200

class ClimateData(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('region', type=str, required=False, help="Region is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        region = get_default_location(user_id, args.get("region"))
        if not region:
            return {"error": "No region provided and no preferences found. Please update your location."}, 400

        data = get_climate_data(region)
        return {"status": "success", "data": data}, 200

class TrendingWeather(Resource):
    def get(self):
        data = get_trending_weather()
        return {"status": "success", "data": data}, 200

class SeasonalChanges(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('region', type=str, required=False, help="Region is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        region = get_default_location(user_id, args.get("region"))
        if not region:
            return {"error": "No region provided and no preferences found. Please update your location."}, 400

        data = get_seasonal_changes(region)
        return {"status": "success", "data": data}, 200

class HistoricalWeather(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        parser.add_argument('date', type=str, required=True, help="Date (YYYY-MM-DD) is required")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_historical_weather(location, args['date'])
        return {"status": "success", "data": data}, 200

class SuggestedActivities(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_suggested_activities(location)
        return {"status": "success", "data": data}, 200

class WeatherRecommendation(Resource):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        data = get_weather_recommendation(user_id)
        return {"status": "success", "data": data}, 200

class PredictionConfidence(Resource):
    @jwt_required()
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('location', type=str, required=False, help="Location is optional")
        args = parser.parse_args()

        user_id = get_jwt_identity()
        location = get_default_location(user_id, args.get("location"))
        if not location:
            return {"error": "No location provided and no preferences found. Please update your location."}, 400

        data = get_prediction_confidence(location)
        return {"status": "success", "data": data}, 200
