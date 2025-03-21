from models import db, Subscription, CustomSubscription
from flask_jwt_extended import get_jwt_identity
import json

def get_weather_alerts(location):
    from services.weather_functions import get_current_weather
    current = get_current_weather(location)
    if not current or "error" in current:
        return {"error": "Weather data not available."}

    current_weather = current.get("current_weather", {})
    if not current_weather:
        return {"error": "No current weather data available."}

    temp = current_weather.get("temperature_celsius")
    wind_speed = current_weather.get("wind_speed_kph")
    description = current_weather.get("weather_description", "").lower()

    alerts = []
    if temp is not None:
        if temp > 35:
            alerts.append("Extreme heat warning: temperatures exceeding 40°C.")
        elif temp > 30:
            alerts.append("High temperature alert: please take precautions in high heat.")

    if wind_speed is not None:
        if wind_speed > 60:
            alerts.append("Severe wind warning: strong gusts detected.")
        elif wind_speed > 40:
            alerts.append("Strong winds expected. Secure loose items outdoors.")

    if "thunderstorm" in description or "rain" in description:
        if "heavy" in description:
            alerts.append("Heavy rain and thunderstorms expected.")
        else:
            alerts.append("Rain and possible thunderstorms detected.")

    if not alerts:
        alerts.append("No severe alerts detected. Conditions are stable.")

    return {"location": location, "alerts": alerts}

ALERT_TYPES = {
    1: "Extreme heat warning (Temperature > 35°C)",
    2: "High temperature warning (Temperature > 30°C)",
    3: "Low temperature warning (Temperature < 5°C)",
    4: "Extreme low temperature warning (Temperature < 15°C)",
    5: "Strong winds warning (Wind speed > 40 km/h)",
    6: "Extreme winds warning (Wind speed > 60 km/h)",
    7: "Rain and possible thunderstorms warning (moderate rain)",
    8: "Heavy rain and thunderstorms warning (heavy rain)"
}

ALERT_TYPE_TEMP = 1
ALERT_TYPE_WIND = 2
ALERT_TYPE_PRECIP = 3

CUSTOM_ALERT_TYPE = {
    ALERT_TYPE_TEMP: "Temperature",
    ALERT_TYPE_WIND: "Wind Speed",
    ALERT_TYPE_PRECIP: "Precipitation Alert"
}

def subscribe_to_alert(user_id, location, alert_type):
    if not alert_type:
        return (
        False, "Invalid alert type. Acceptable values are: " + ", ".join([f"{k}: {v}" for k, v in ALERT_TYPES.items()]))
    try:
        alert_type = int(alert_type)
    except ValueError:
        return (
        False, "Invalid alert type. Acceptable values are: " + ", ".join([f"{k}: {v}" for k, v in ALERT_TYPES.items()]))
    if alert_type not in ALERT_TYPES:
        return (
        False, "Invalid alert type. Acceptable values are: " + ", ".join([f"{k}: {v}" for k, v in ALERT_TYPES.items()]))

    existing = Subscription.query.filter_by(user_id=user_id, location=location, alert_type=alert_type).first()
    if existing:
        return (False,
                f"User {user_id} is already subscribed to alert type {alert_type} ({ALERT_TYPES[alert_type]}) for {location}.")

    subscription = Subscription(user_id=user_id, location=location, alert_type=alert_type)
    db.session.add(subscription)
    try:
        db.session.commit()
        return (
        True, f"User {user_id} subscribed to alert type {alert_type} ({ALERT_TYPES[alert_type]}) for {location}.")
    except Exception as e:
        db.session.rollback()
        return (False, f"An error occurred: {str(e)}")

def create_custom_alert(user_id, location, condition, operator=None, threshold=None):
    condition_lower = condition.lower().strip() if condition else ""
    mapping = {
        "temperature": ALERT_TYPE_TEMP,
        "wind_speed": ALERT_TYPE_WIND,
        "precipitation": ALERT_TYPE_PRECIP
    }
    alert_type = mapping.get(condition_lower)
    if alert_type is None:
        return False, "Condition must be 'temperature', 'wind_speed', or 'precipitation'."

    if alert_type in (ALERT_TYPE_TEMP, ALERT_TYPE_WIND):
        if not operator or operator.strip() not in (">", "<"):
            return False, "Temperature and wind speed alerts require an operator ('>' or '<')."
        operator = operator.strip()
        if threshold is None:
            return False, "Threshold must be provided for temperature and wind speed alerts."
        try:
            float(threshold)
        except (ValueError, TypeError):
            return False, "Threshold must be a numeric value for temperature and wind speed alerts."
    elif alert_type == ALERT_TYPE_PRECIP:
        valid_mapping = {
            "no rain": "no rain",
            "clear": "no rain",
            "cloud": "no rain",
            "clouds": "no rain",
            "cloudy": "no rain",
            "sunny": "no rain",
            "light": "light",
            "moderate": "moderate",
            "heavy": "heavy"
        }
        if not threshold or threshold.lower().strip() not in valid_mapping:
            return False, ("Precipitation threshold must be one of: no rain, clear, cloud, clouds, cloudy, sunny, light, moderate, or heavy.")
        operator = None
        threshold = valid_mapping[threshold.lower().strip()]

    existing = CustomSubscription.query.filter_by(
        user_id=user_id,
        location=location,
        alert_type=alert_type,
        operator=operator,
        threshold=str(threshold)
    ).first()
    if existing:
        return False, f"A subscription for this alert already exists at {location}."

    subscription = CustomSubscription(
        user_id=user_id,
        location=location,
        alert_type=alert_type,
        operator=operator,
        threshold=str(threshold)
    )
    db.session.add(subscription)
    try:
        db.session.commit()
        return True, f"Custom alert for {CUSTOM_ALERT_TYPE.get(alert_type, 'Unknown')} at {location} created."
    except Exception as e:
        db.session.rollback()
        return False, f"An error occurred: {str(e)}"

def get_custom_alert_description(alert_json):
    try:
        alert_data = json.loads(alert_json)
    except Exception:
        return "Unknown custom alert"

    category = alert_data.get("category")
    if category == 1:
        operator = alert_data.get("operator", "?")
        threshold = alert_data.get("threshold", "?")
        return f"Temperature {operator} {threshold}°C"
    elif category == 2:
        threshold = alert_data.get("threshold", "?")
        return f"Wind speed > {threshold} km/h"
    elif category == 3:
        precip_mapping = {0: "No rain", 1: "Light rain", 2: "Moderate rain", 3: "Heavy rain"}
        condition = alert_data.get("precip_condition")
        description = precip_mapping.get(condition, "Unknown")
        return f"Precipitation alert: {description}"
    else:
        return "Unknown custom alert"

def map_precipitation_category(description):
    desc = description.lower() if description else ""

    no_rain_keywords = [
        "clear sky", "mainly clear", "partly cloudy", "overcast", "fog", "depositing rime fog"
    ]
    for word in no_rain_keywords:
        if word in desc:
            return "no rain"

    light_keywords = [
        "light drizzle", "light freezing drizzle", "slight rain",
        "slight rain showers", "slight snow fall", "slight snow showers", "snow grains"
    ]
    for word in light_keywords:
        if word in desc:
            return "light"

    moderate_keywords = [
        "moderate drizzle", "moderate rain", "moderate rain showers",
        "moderate snow fall", "moderate snow showers", "slight or moderate thunderstorm",
        "thunderstorm with slight hail"
    ]
    for word in moderate_keywords:
        if word in desc:
            return "moderate"

    heavy_keywords = [
        "dense drizzle", "dense freezing drizzle", "heavy rain",
        "heavy freezing rain", "heavy snow fall", "heavy rain showers",
        "heavy snow showers", "thunderstorm with heavy hail"
    ]
    for word in heavy_keywords:
        if word in desc:
            return "heavy"

    return "unknown"

def evaluate_normal_alert(subscription, weather):
    cw = weather.get("current_weather", {})
    if not cw:
        return None

    temp = cw.get("temperature_celsius")
    wind = cw.get("wind_speed_kph")
    desc = cw.get("weather_description", "").lower()
    alert_type = subscription.alert_type

    if alert_type == "1":
        if temp is not None and temp > 35:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, exceeding 35°C."
    elif alert_type == "2":
        if temp is not None and temp > 30:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, exceeding 30°C."
    elif alert_type == "3":
        if temp is not None and temp < 5:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, below 5°C."
    elif alert_type == "4":
        if temp is not None and temp < 15:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, below 15°C."
    elif alert_type == "5":
        if wind is not None and wind > 40:
            return f"Alert: Wind speed at {subscription.location} is {wind} km/h, exceeding 40 km/h."
    elif alert_type == "6":
        if wind is not None and wind > 60:
            return f"Alert: Wind speed at {subscription.location} is {wind} km/h, exceeding 60 km/h."
    elif alert_type == "7":
        current_category = map_precipitation_category(cw.get("weather_description", ""))
        if current_category == "moderate":
            return f"Alert: Precipitation at {subscription.location} is moderate."
    elif alert_type == "8":
        current_category = map_precipitation_category(cw.get("weather_description", ""))
        if current_category == "heavy":
            return f"Alert: Heavy rain detected at {subscription.location}."
    return None

def evaluate_custom_alert(subscription, weather):
    cw = weather.get("current_weather", {})
    if not cw:
        return None

    if subscription.alert_type == ALERT_TYPE_TEMP:
        try:
            thresh = float(subscription.threshold)
        except:
            return None
        temp = cw.get("temperature_celsius")
        if temp is None:
            return None
        if subscription.operator == ">" and temp > thresh:
            return f"Temperature at {subscription.location} is {temp}°C, exceeding {subscription.threshold}°C."
        elif subscription.operator == "<" and temp < thresh:
            return f"Temperature at {subscription.location} is {temp}°C, below {subscription.threshold}°C."
    elif subscription.alert_type == ALERT_TYPE_WIND:
        try:
            thresh = float(subscription.threshold)
        except:
            return None
        wind = cw.get("wind_speed_kph")
        if wind is None:
            return None
        if subscription.operator == ">" and wind > thresh:
            return f"Wind speed at {subscription.location} is {wind} km/h, exceeding {subscription.threshold} km/h."
        elif subscription.operator == "<" and wind < thresh:
            return f"Wind speed at {subscription.location} is {wind} km/h, below {subscription.threshold} km/h."
    elif subscription.alert_type == ALERT_TYPE_PRECIP:
        current_category = map_precipitation_category(cw.get("weather_description", ""))
        subscribed_category = subscription.threshold.lower().strip()
        if current_category == subscribed_category:
            return f"Precipitation at {subscription.location} is '{current_category}'."
    return None

def cancel_alert(args):
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
            alert_type=str(alert_type_int)
        ).first()

        if subscription:
            db.session.delete(subscription)
            db.session.commit()
            return {"status": "success", "message": f"Cancelled normal alert type {alert_type_int} ({ALERT_TYPES.get(alert_type_int, 'Unknown')}) for {location}."}, 200
        else:
            return {"status": "error", "message": f"No active normal subscription for alert type {alert_type_int} in {location}."}, 400

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



