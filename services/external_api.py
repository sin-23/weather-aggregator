# services/external_api.py
import requests, re
from config import Config
import datetime
from datetime import date, timedelta

# In-memory stores for persistence (for demonstration only)
user_preferences = {}  # Maps user_id to preferences
user_locations = {}  # Maps user_id to their location
feedback_store = {}  # Maps user_id to list of feedback messages
subscriptions = {}  # Maps (location, alert_type) or (location, condition) to subscription details


def geocode_location(location):
    """
    Uses OpenStreetMap Nominatim API to convert a location name into latitude and longitude.
    It requests up to 5 results and selects the best candidate by 'importance'.
    The function forces English results and checks if the candidate's display_name (in English)
    contains the query (as a substring, case-insensitive). If not, it returns (None, None).
    """
    location = location.strip()
    if not location:
        return None, None

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": location,
        "format": "json",
        "addressdetails": 1,
        "limit": 5
    }
    headers = {
        "User-Agent": "WeatherAggregatorAPI/1.0 (youremail@example.com)",
        "Accept-Language": "en"  # Force English output for display_name.
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            # Sort results by 'importance' in descending order.
            sorted_results = sorted(data, key=lambda x: x.get("importance", 0), reverse=True)
            best = sorted_results[0]
            display_name = best.get("display_name", "").lower()
            query_lower = location.lower()
            importance = best.get("importance", 0)
            # Accept the candidate if the query appears anywhere in the display_name
            # (case-insensitive), or if the importance is high enough.
            if query_lower not in display_name and importance < 0.1:
                return None, None
            lat = float(best.get("lat"))
            lon = float(best.get("lon"))
            return lat, lon
        else:
            return None, None
    except Exception as e:
        print("Geocoding error:", e)
        return None, None


def get_current_weather(location):
    """
    Fetches current weather data for a given location using Open-Meteo.
    """
    lat, lon = geocode_location(location)
    if lat is None or lon is None:
        return {"error": "Could not geocode location."}

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_forecast(location, start_date=None):
    """
    Fetches a daily summary 7-day forecast for a given location.
    If start_date is provided (in YYYY-MM-DD format), the forecast starts from that day.
    Otherwise, it defaults to the next 7 days starting today.
    """
    lat, lon = geocode_location(location)
    if lat is None or lon is None:
        return {"error": "Could not geocode location."}

    from datetime import date, timedelta
    # Use today's date if no start_date is provided.
    if start_date is None:
        start_date_obj = date.today()
    else:
        try:
            start_date_obj = date.fromisoformat(start_date)
        except Exception as e:
            return {"error": "Invalid start_date format. Use YYYY-MM-DD."}
    # End date is 6 days after start_date (for a total of 7 days)
    end_date = (start_date_obj + timedelta(days=6)).isoformat()
    start_date = start_date_obj.isoformat()

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "auto"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}



def get_weather_alerts(location):
    """
    Fetches weather alerts by checking the forecast.
    For example, if the precipitation for today exceeds a threshold, an alert is returned.
    """
    forecast = get_forecast(location)
    try:
        # For simplicity, check today's precipitation value
        precip = forecast.get("daily", {}).get("precipitation_sum", [0])[0]
        if precip > 10:
            return {"location": location, "alerts": "Heavy rainfall expected."}
        else:
            return {"location": location, "alerts": "No severe alerts."}
    except Exception as e:
        return {"error": str(e)}


def subscribe_to_alert(location, alert_type):
    """
    Stores a subscription for weather alerts in an in-memory dictionary.
    """
    key = (location, alert_type)
    subscriptions[key] = {
        "location": location,
        "alert_type": alert_type,
        "subscribed_at": datetime.datetime.now().isoformat()
    }
    return f"Subscribed to {alert_type} alerts for {location}."


def cancel_alert(location, alert_type):
    """
    Cancels a previously stored alert subscription.
    """
    key = (location, alert_type)
    if key in subscriptions:
        del subscriptions[key]
        return f"Cancelled {alert_type} alerts for {location}."
    else:
        return f"No active subscription for {alert_type} alerts in {location}."


def create_custom_alert(location, condition):
    """
    Creates a custom alert by storing it in the in-memory subscriptions store.
    """
    key = (location, condition)
    subscriptions[key] = {
        "location": location,
        "condition": condition,
        "created_at": datetime.datetime.now().isoformat()
    }
    return f"Custom alert for condition '{condition}' in {location} created."


def compare_weather(locations):
    """
    Compares current weather data for multiple locations.
    Expects 'locations' to be a list of location names.
    """
    results = {}
    for loc in locations:
        results[loc] = get_current_weather(loc)
    return results


def get_climate_data(region):
    """
    Fetches climate data over the past 30 days for a given region.
    It computes average maximum and minimum temperatures and precipitation.
    """
    lat, lon = geocode_location(region)
    if lat is None or lon is None:
        return {"error": "Could not geocode region."}

    from datetime import date, timedelta
    # End date is yesterday (to ensure complete data)
    end_date = date.today() - timedelta(days=1)
    # Start date is 29 days before the end date (to cover 30 days)
    start_date = end_date - timedelta(days=29)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        daily = data.get("daily", {})
        # Filter out any None values from the lists
        temps_max = [t for t in daily.get("temperature_2m_max", []) if t is not None]
        temps_min = [t for t in daily.get("temperature_2m_min", []) if t is not None]
        precip = [p for p in daily.get("precipitation_sum", []) if p is not None]
        if temps_max and temps_min and precip:
            avg_max = sum(temps_max) / len(temps_max)
            avg_min = sum(temps_min) / len(temps_min)
            avg_precip = sum(precip) / len(precip)
            return {
                "region": region,
                "average_max_temp": f"{avg_max:.1f}°C",
                "average_min_temp": f"{avg_min:.1f}°C",
                "average_precipitation": f"{avg_precip:.1f} mm"
            }
        else:
            return {"error": "No climate data available."}
    except Exception as e:
        return {"error": str(e)}


def get_trending_weather():
    """
    Fetches current weather for a list of major cities.
    """
    cities = ["New York", "London", "Tokyo", "Sydney", "Paris"]
    results = {}
    for city in cities:
        results[city] = get_current_weather(city)
    return {"trending_weather": results}


def get_seasonal_changes(region):
    """
    Compares current weather to the same day last year (using historical data)
    to indicate seasonal changes.
    """
    lat, lon = geocode_location(region)
    if lat is None or lon is None:
        return {"error": "Could not geocode region."}

    current = get_current_weather(region)
    last_year_date = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": last_year_date,
        "end_date": last_year_date,
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "auto"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        historical = response.json()
        historical_daily = historical.get("daily", {})
        if not historical_daily.get("temperature_2m_max") or not historical_daily.get("temperature_2m_min"):
            return {"error": "No historical data available."}
        historical_max = historical_daily["temperature_2m_max"][0]
        historical_min = historical_daily["temperature_2m_min"][0]
        current_temp = current.get("current_weather", {}).get("temperature", None)
        if current_temp is None:
            return {"error": "No current temperature available."}
        historical_avg = (historical_max + historical_min) / 2
        change = current_temp - historical_avg
        return {
            "region": region,
            "current_temperature": f"{current_temp}°C",
            "historical_average": f"{historical_avg:.1f}°C",
            "change": f"{change:.1f}°C"
        }
    except Exception as e:
        return {"error": str(e)}


def save_user_preferences(user_id, preferences):
    """
    Saves user preferences in an in-memory store.
    """
    global user_preferences
    user_preferences[user_id] = preferences
    return f"Preferences for user {user_id} saved."


def get_suggested_activities(location):
    """
    Suggests activities based on the current temperature.
    """
    weather = get_current_weather(location)
    try:
        temp = weather.get("current_weather", {}).get("temperature", 20)
        if temp > 25:
            activities = ["Go swimming", "Have a picnic"]
        elif temp > 15:
            activities = ["Go hiking", "Cycle in the park"]
        else:
            activities = ["Visit a museum", "Read a book indoors"]
    except Exception:
        activities = ["General indoor activity"]
    return {"location": location, "suggested_activities": activities}


def get_weather_recommendation(user_id):
    """
    Provides a weather-based recommendation based on the user's stored location.
    """
    global user_locations
    location = user_locations.get(user_id, "New York")  # Default if not set
    weather = get_current_weather(location)
    temp = weather.get("current_weather", {}).get("temperature", 20)
    if temp > 25:
        recommendation = "It's hot outside. Wear light clothing and stay hydrated."
    elif temp < 10:
        recommendation = "It's cold. Bundle up and wear warm clothes."
    else:
        recommendation = "The weather is moderate. Enjoy your day!"
    return {"user_id": user_id, "location": location, "recommendation": recommendation}


def get_prediction_confidence(location):
    """
    Computes a rough prediction confidence based on the difference between
    current temperature and the average forecasted maximum.
    """
    current = get_current_weather(location)
    forecast = get_forecast(location)
    try:
        current_temp = current.get("current_weather", {}).get("temperature")
        forecast_temps = forecast.get("daily", {}).get("temperature_2m_max", [])
        if forecast_temps and current_temp is not None:
            forecast_avg = sum(forecast_temps) / len(forecast_temps)
            diff = abs(current_temp - forecast_avg)
            confidence = max(0, 100 - diff * 5)  # Arbitrary formula for demonstration
            return {"location": location, "confidence": f"{confidence:.0f}%"}
        else:
            return {"error": "Forecast data unavailable for prediction confidence."}
    except Exception as e:
        return {"error": str(e)}


def update_user_location(user_id, location):
    """
    Updates a user's location in an in-memory store.
    """
    global user_locations
    user_locations[user_id] = location
    return f"User {user_id}'s location updated to {location}."


def get_historical_weather(location, date):
    """
    Fetches historical weather data for a given location and date using Open-Meteo's archive API.
    The 'date' should be in YYYY-MM-DD format.
    """
    lat, lon = geocode_location(location)
    if lat is None or lon is None:
        return {"error": "Could not geocode location."}

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def submit_feedback(user_id, feedback):
    """
    Stores user feedback in an in-memory list.
    """
    global feedback_store
    if user_id not in feedback_store:
        feedback_store[user_id] = []
    feedback_store[user_id].append(feedback)
    return f"Feedback from user {user_id} recorded."


def get_realtime_weather(location):
    """
    Fetches current weather data and enhances it with additional details
    like humidity, pressure, and visibility. These extra fields are added
    as dummy values since the Open-Meteo current weather endpoint might not provide them.
    """
    # Call the existing basic current weather function
    data = get_current_weather(location)
    if "error" in data:
        return data

    # Extract the basic current weather details
    current = data.get("current_weather", {})

    # Enhance with additional details (these are dummy values for demonstration)
    current["humidity"] = 60  # Example: 60% humidity
    current["pressure"] = 1013  # Example: 1013 hPa
    current["visibility"] = 10  # Example: 10 km visibility

    # Replace the basic current_weather with the enhanced version
    data["current_weather"] = current
    return data


def get_detailed_forecast(location):
    """
    Fetches a detailed (hourly) forecast for the next 48 hours using WeatherAPI.com.
    This version filters the response to only include a subset of fields (time, temp_c, and condition text).
    """
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": Config.WEATHERAPI_KEY,
        "q": location,
        "days": 3,  # Request forecast for 3 days (to cover at least 48 hours)
        "aqi": "no",
        "alerts": "no"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract forecast data from the first 2 forecast days
        forecast_days = data.get("forecast", {}).get("forecastday", [])
        hourly_data = []
        for day in forecast_days:
            hourly = day.get("hour", [])
            hourly_data.extend(hourly)

        # Only take the next 48 hours
        hourly_data = hourly_data[:48]

        # Filter each hourly entry to include only a few keys:
        filtered_hourly = []
        for entry in hourly_data:
            filtered_entry = {
                "time": entry.get("time"),
                "temp_c": entry.get("temp_c"),
                "condition": entry.get("condition", {}).get("text")
            }
            filtered_hourly.append(filtered_entry)

        # Return a simplified response
        detailed_forecast = {
            "location": data.get("location", {}),
            "hourly": filtered_hourly
        }
        return detailed_forecast
    except Exception as e:
        return {"error": str(e)}
