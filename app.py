# app.py
from flask import Flask, jsonify, request
from flask_restful import Api
from flask_jwt_extended import JWTManager
from config import Config
from models import db  # Import SQLAlchemy object

# Import resource classes from the resources package
from resources.weather import CurrentWeather, ForecastWithDate, RealTimeWeather, Next7DaysForecast, DetailedForecast
from resources.alerts import WeatherAlerts, SubscribeAlert, CancelAlert, CustomAlert
from resources.comparisons import CompareWeather, ClimateData, TrendingWeather, SeasonalChanges
from resources.personalization import UserPreferences, SuggestedActivities, WeatherRecommendation, PredictionConfidence, UpdateLocation
from resources.utilities import HistoricalWeather, FeedbackResource, AverageRatingResource
from auth import UserRegistration, UserLogin, ProtectedResource

from services.external_api import create_custom_alert

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
api = Api(app)
jwt = JWTManager(app)

# Create the database tables if they don’t exist
with app.app_context():
     # add lang to if uulitin database: db.drop_all()   # This will remove all existing tables.
    db.create_all() # This will create tables based on your current models.


# Register Weather Endpoints
api.add_resource(CurrentWeather, '/weather/current')
api.add_resource(ForecastWithDate, '/weather/forecast')
api.add_resource(RealTimeWeather, '/weather/real-time')
api.add_resource(Next7DaysForecast, '/weather/next-7-days')
api.add_resource(DetailedForecast, '/weather/forecast/detailed')


# Register Alerts Endpoints
api.add_resource(WeatherAlerts, '/weather/alerts')
api.add_resource(SubscribeAlert, '/weather/alert/subscribe')
api.add_resource(CancelAlert, '/weather/alert/cancel')
api.add_resource(CustomAlert, '/weather/custom-alert')

# Register Comparison Endpoints
api.add_resource(CompareWeather, '/weather/compare')
api.add_resource(ClimateData, '/weather/climate')
api.add_resource(TrendingWeather, '/weather/trending')
api.add_resource(SeasonalChanges, '/weather/seasonal-changes')

# Register Personalization Endpoints
api.add_resource(UserPreferences, '/weather/preferences')
api.add_resource(SuggestedActivities, '/weather/suggested-activities')
api.add_resource(WeatherRecommendation, '/weather/recommendation')
api.add_resource(PredictionConfidence, '/weather/prediction-confidence')
api.add_resource(UpdateLocation, '/weather/update-location')

# Register Utility Endpoints
api.add_resource(HistoricalWeather, '/weather/historical')
api.add_resource(FeedbackResource, '/weather/feedback')
api.add_resource(AverageRatingResource, '/feedback/average')

# Register authentication endpoints
api.add_resource(UserRegistration, '/register')
api.add_resource(UserLogin, '/login')
api.add_resource(ProtectedResource, '/protected')

# Global Error Handlers
@app.errorhandler(400)
def bad_request(error):
    return jsonify({"status": "error", "message": "Bad Request"}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Resource Not Found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"status": "error", "message": "Internal Server Error"}), 500


# @app.route('/api/custom-alert', methods=['POST'])
# def api_create_alert():
#     data = request.get_json()
#     user_id = data.get("user_id")
#     location = data.get("location")
#     condition = data.get("condition")
#     operator = data.get("operator")  # Expecting something like ">" or "<"
#     threshold = data.get("threshold")
#
#     result = create_custom_alert(user_id, location, condition, operator, threshold)
#     if result.startswith("Error:"):
#         return jsonify({"status": "error", "message": result}), 400
#     return jsonify({"status": "success", "message": result}), 201

if __name__ == '__main__':
    app.run(debug=True)
