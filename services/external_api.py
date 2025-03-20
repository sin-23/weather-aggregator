# services/external_api.py
import requests, re
from config import Config
from datetime import date, timedelta, datetime
import difflib
from flask import Flask, request, jsonify
from models import db, Subscription, UserPreference, UserLocation, Feedback, UserSearchHistory, CustomSubscription
from bs4 import BeautifulSoup
from flask_jwt_extended import get_jwt_identity, jwt_required
from collections import Counter
from sqlalchemy import desc
import json

# In-memory stores for persistence (for demonstration only)
user_preferences = {}  # Maps user_id to preferences
user_locations = {}  # Maps user_id to their location
feedback_store = {}  # Maps user_id to list of feedback messages
subscriptions = {}  # Maps (location, alert_type) or (location, condition) to subscription details

def log_user_search(user_id, location):
    """
    Logs a user's search for a given location. If a record for that user and location exists,
    increments the search_count and updates the last_searched timestamp. Otherwise, creates a new record.
    Then updates the user's preferences with the top searched locations.
    """
    record = UserSearchHistory.query.filter_by(user_id=user_id, location=location).first()
    if record:
        record.search_count += 1
        record.last_searched = datetime.utcnow()
    else:
        record = UserSearchHistory(user_id=user_id, location=location, search_count=1)
        db.session.add(record)
    db.session.commit()

    # Update preferences based on the entire search history for this user.
    update_user_preferences_from_history(user_id)


def update_user_preferences_from_history(user_id):
    """
    Retrieves the user's search history from UserSearchHistory, orders the records by search_count descending,
    takes the top 5 locations, and updates (or creates) the UserPreference record accordingly.
    """
    # Query the top 5 search history entries for the user, ordered by frequency.
    search_history = UserSearchHistory.query.filter_by(user_id=user_id) \
        .order_by(desc(UserSearchHistory.search_count)) \
        .limit(5).all()
    # Build a list of locations in descending order of frequency.
    top_locations = [record.location for record in search_history]

    # Update the UserPreference record.
    user_pref = UserPreference.query.filter_by(user_id=user_id).first()
    if user_pref:
        user_pref.top_searches = top_locations
    else:
        user_pref = UserPreference(user_id=user_id, top_searches=top_locations)
        db.session.add(user_pref)
    db.session.commit()

def normalize(text):
    return text.strip().lower() if text else ""

def geocode_location(location):
    location = location.strip()
    if not location:
        return None
    query_norm = normalize(location)
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": location,
        "format": "json",
        "addressdetails": 1,
        "limit": 5
    }
    headers = {
        "User-Agent": "WeatherAggregatorAPI/1.0 (youremail@example.com)",
        "Accept-Language": "en"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            print(f"No results found for '{location}'")
            return None
        sorted_results = sorted(data, key=lambda x: x.get("importance", 0), reverse=True)
        threshold = 0.65  # Lowered threshold to allow minor typos
        for candidate in sorted_results:
            address = candidate.get("address", {})
            candidate_fields = []
            for field in ["city", "town", "village", "locality", "county", "state", "country"]:
                if field in address:
                    candidate_fields.append(address[field])
            if candidate.get("display_name"):
                candidate_fields.append(candidate.get("display_name"))
            for field in candidate_fields:
                norm_field = normalize(field)
                # Accept if the query appears as a substring...
                if query_norm in norm_field:
                    lat = float(candidate.get("lat"))
                    lon = float(candidate.get("lon"))
                    name = address.get("city") or address.get("town") or address.get("village") or address.get("locality") or candidate.get("display_name")
                    region = address.get("state") or address.get("county")
                    country = address.get("country")
                    return {"lat": lat, "lon": lon, "name": name, "region": region, "country": country}
                else:
                    # ...or if the similarity ratio is above the threshold.
                    ratio = difflib.SequenceMatcher(None, query_norm, norm_field).ratio()
                    if ratio >= threshold:
                        lat = float(candidate.get("lat"))
                        lon = float(candidate.get("lon"))
                        name = address.get("city") or address.get("town") or address.get("village") or address.get("locality") or candidate.get("display_name")
                        region = address.get("state") or address.get("county")
                        country = address.get("country")
                        return {"lat": lat, "lon": lon, "name": name, "region": region, "country": country}
        print(f"Location '{location}' not found with sufficient confidence.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Geocoding error: {e}")
        return None

def get_weather_description(code):
    """
    Converts a numeric weather code into a human-readable description.
    """
    weather_code_map = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Heavy rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Slight or moderate thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }
    return weather_code_map.get(code, "Unknown")


def get_current_weather(location, user_id=None):
    """
    Fetches current weather data for a given location using Open-Meteo.
    If a user_id is provided, logs the search for that user.
    Returns a JSON with geocode details (name, region, country) at the top,
    and a combined current_weather block with human-friendly values.
    """
    # Log the search if user_id is provided.
    if user_id:
        log_user_search(user_id, location)

    geocode_result = geocode_location(location)
    if geocode_result is None:
        return {"error": f"Could not geocode location '{location}'."}
    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        weather_data = response.json()
        # Remove unwanted keys.
        for key in ["generationtime_ms", "utc_offset_seconds", "timezone", "timezone_abbreviation"]:
            weather_data.pop(key, None)
        current = weather_data.get("current_weather", {})
        formatted_current = {
            "temperature_celsius": current.get("temperature"),
            "wind_speed_kph": current.get("windspeed"),
            "wind_direction": current.get("winddirection"),
            "is_day": True if current.get("is_day") == 1 else False,
            "weather_description": get_weather_description(current.get("weathercode"))
        }
        result = {"geocode": geocode_details, "current_weather": formatted_current}
        return result
    except Exception as e:
        return {"error": str(e)}


def get_forecast(location, start_date=None):
    """
    Fetches a daily summary 7-day forecast for a given location.
    If start_date is provided (in YYYY-MM-DD format), the forecast starts from that day.
    Otherwise, it defaults to the next 7 days starting today.
    """
    # Get geocode details
    geocode_result = geocode_location(location)
    if geocode_result is None:
        return {"error": f"Could not geocode location '{location}'."}

    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    # Determine start and end dates
    if start_date is None:
        start_date_obj = date.today()
    else:
        try:
            start_date_obj = date.fromisoformat(start_date)
        except ValueError:
            return {"error": "Invalid start_date format. Use YYYY-MM-DD."}

    end_date = (start_date_obj + timedelta(days=6)).isoformat()
    start_date = start_date_obj.isoformat()

    # API Request
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode",
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Format daily weather data with human-readable weather codes
        daily_data = []
        for i in range(len(data["daily"]["time"])):
            daily_entry = {
                "date": data["daily"]["time"][i],
                "max_temp": f"{data['daily']['temperature_2m_max'][i]}°C",
                "min_temp": f"{data['daily']['temperature_2m_min'][i]}°C",
                "precipitation": f"{data['daily']['precipitation_sum'][i]} mm",
                "weather": get_weather_description(data["daily"]["weathercode"][i])
            }
            daily_data.append(daily_entry)

        # Final structured response
        result = {
            "geocode": geocode_details,
            "forecast": daily_data
        }
        return result

    except Exception as e:
        return {"error": str(e)}


def get_forecast_with_date(location, start_date):
    """
    Fetches a daily summary 7-day forecast for a given location starting from the provided start_date.
    The start_date must be in YYYY-MM-DD format and within the next 7 days.
    If the start_date is too far in the future, returns an error message.
    """
    # Validate the start_date format.
    try:
        start_date_obj = date.fromisoformat(start_date)
    except ValueError:
        return {"error": "Invalid start_date format. Use YYYY-MM-DD."}

    # Check if the start_date is within the next 7 days.
    max_forecast_date = date.today() + timedelta(days=7)
    if start_date_obj > max_forecast_date:
        return {"error": "start_date is too far in the future. Please choose a date within the next 7 days."}

    # If valid, call the existing get_forecast function.
    return get_forecast(location, start_date)


def get_weather_alerts(location):
    """
    Fetches weather alerts for a given location using real-time weather data
    from get_current_weather. It analyzes the current temperature, wind speed,
    and weather description to generate alerts for severe conditions.

    Alerts Conditions:
      - Temperature:
          >40°C: "Extreme heat warning"
          >38°C: "High temperature alert"
      - Wind Speed:
          >60 km/h: "Severe wind warning"
          >40 km/h: "Strong winds expected"
      - Weather Description:
          If it contains "thunderstorm" or "rain":
              if it contains "heavy": "Heavy rain and thunderstorms expected"
              else: "Rain and possible thunderstorms detected"
      - If none of the above, it returns a general advisory.
    """
    # Get current weather data (which includes geocode details)
    current = get_current_weather(location)
    if not current or "error" in current:
        return {"error": "Weather data not available."}

    current_weather = current.get("current_weather", {})
    if not current_weather:
        return {"error": "No current weather data available."}

    # Extract values (assumed to be numeric) and description
    temp = current_weather.get("temperature_celsius")  # should be numeric
    wind_speed = current_weather.get("wind_speed_kph")
    description = current_weather.get("weather_description", "").lower()

    alerts = []
    # Check temperature-based alerts
    if temp is not None:
        if temp > 35:
            alerts.append("Extreme heat warning: temperatures exceeding 40°C.")
        elif temp > 30:
            alerts.append("High temperature alert: please take precautions in high heat.")

    # Check wind speed alerts
    if wind_speed is not None:
        if wind_speed > 60:
            alerts.append("Severe wind warning: strong gusts detected.")
        elif wind_speed > 40:
            alerts.append("Strong winds expected. Secure loose items outdoors.")

    # Check precipitation/thunderstorm alerts based on weather description
    if "thunderstorm" in description or "rain" in description:
        if "heavy" in description:
            alerts.append("Heavy rain and thunderstorms expected.")
        else:
            alerts.append("Rain and possible thunderstorms detected.")

    # If no alert conditions met, provide a general advisory.
    if not alerts:
        alerts.append("No severe alerts detected. Conditions are stable.")

    return {"location": location, "alerts": alerts}


def compare_weather(locations):
    """
    Compares current weather data for multiple locations.
    Expects 'locations' to be a list of location names.
    For each location, it fetches the weather using get_current_weather,
    which returns data with the values merged with their units and geocode details at the top.
    """
    results = {}
    for loc in locations:
        weather = get_current_weather(loc)
        # If there's an error, store the error message.
        if "error" in weather:
            results[loc] = {"error": weather["error"]}
        else:
            results[loc] = weather
    return results


def get_climate_data(region):
    """
    Fetches climate data over the past 30 days for a given region.
    It computes average maximum and minimum temperatures and precipitation.
    """
    # Get geocode details
    geocode_result = geocode_location(region)
    if geocode_result is None:
        return {"error": f"Could not geocode region '{region}'."}

    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    # Define start and end dates for the past 30 days
    end_date = date.today() - timedelta(days=1)  # End date is yesterday
    start_date = end_date - timedelta(days=29)  # Start date is 29 days before

    # API Request
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

        # Extract and filter climate data
        temps_max = [t for t in daily.get("temperature_2m_max", []) if t is not None]
        temps_min = [t for t in daily.get("temperature_2m_min", []) if t is not None]
        precip = [p for p in daily.get("precipitation_sum", []) if p is not None]

        if temps_max and temps_min and precip:
            avg_max = sum(temps_max) / len(temps_max)
            avg_min = sum(temps_min) / len(temps_min)
            avg_precip = sum(precip) / len(precip)

            result = {
                "geocode": geocode_details,
                "climate_summary": {
                    "average_max_temp": f"{avg_max:.1f}°C",
                    "average_min_temp": f"{avg_min:.1f}°C",
                    "average_precipitation": f"{avg_precip:.1f} mm"
                }
            }
            return result
        else:
            return {"error": "No climate data available."}

    except Exception as e:
        return {"error": str(e)}


def get_trending_cities():
    """
    Scrapes Wikipedia's "Wikipedia:WikiProject_Cities/Popular_pages" page to obtain
    a list of trending (largest) cities from the "Page title" column.
    It reads the second cell of each row, skips any row containing "List of",
    and returns the top 5 unique city names. If a candidate contains "new york" or is
    one of the specified boroughs (Brooklyn, Manhattan, Queens, Bronx, Staten Island),
    it is normalized to "new york" to avoid duplicate entries.
    """
    from bs4 import BeautifulSoup
    import requests

    url = "https://en.wikipedia.org/wiki/Wikipedia:WikiProject_Cities/Popular_pages"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="wikitable")
        trending = []
        seen = set()
        rows = table.find_all("tr")[1:]  # Skip header row.
        for row in rows:
            if len(trending) >= 5:
                break
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            candidate = cells[1].get_text(strip=True)
            if "List of" in candidate:
                continue

            # Normalize candidate text.
            normalized_candidate = candidate.lower().strip()

            # Custom normalization: treat any candidate containing "new york" or being one of the boroughs as "new york"
            if "new york" in normalized_candidate or normalized_candidate in ("brooklyn", "manhattan", "queens", "bronx", "staten island"):
                normalized_candidate = "new york"

            if normalized_candidate in seen:
                continue

            trending.append(candidate)
            seen.add(normalized_candidate)
        return trending
    except Exception as e:
        print("Error scraping trending cities from Wikipedia:", e)
        return []


def get_trending_weather():
    """
    Fetches current weather for trending cities determined dynamically by scraping Wikipedia.
    If scraping fails or returns an empty list, falls back to a preset list.
    """
    trending_cities = get_trending_cities()
    if not trending_cities:
        trending_cities = ["Chicago", "London", "Tokyo", "Sydney", "Paris"]
    results = {}
    for city in trending_cities:
        results[city] = get_current_weather(city)
    return {"trending_weather": results}


def get_seasonal_changes(region):
    """
    Compares current weather to the same day last year to indicate seasonal changes.
    Returns a dictionary with geocode details at the top and a seasonal summary.
    """
    # Get geocode details for the region.
    geocode_result = geocode_location(region)
    if geocode_result is None:
        return {"error": f"Could not geocode region '{region}'."}
    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    # Get current weather data.
    current = get_current_weather(region)
    if not current or "error" in current:
        return {"error": "No current weather data available."}

    # Look for the temperature under 'temperature_celsius'
    current_temp = current.get("current_weather", {}).get("temperature_celsius")
    if current_temp is None:
        return {"error": "No current temperature available."}

    # Calculate the date for the same day last year.
    last_year_date = (date.today() - timedelta(days=365)).isoformat()
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
        historical_avg = (historical_max + historical_min) / 2
        change = current_temp - historical_avg

        seasonal_summary = {
            "current_temperature": f"{current_temp}°C",
            "historical_average": f"{historical_avg:.1f}°C",
            "temperature_change": f"{change:.1f}°C"
        }
        result = {
            "geocode": geocode_details,
            "seasonal_changes": seasonal_summary
        }
        return result
    except Exception as e:
        return {"error": str(e)}


def get_suggested_activities(location):
    """
    Suggests activities based on the current temperature.
    If weather data is not available, returns an error message.
    """
    weather = get_current_weather(location)
    if not weather or "error" in weather:
        return {"location": location, "error": "Weather data not available."}

    current_weather = weather.get("current_weather", {})
    # Use the key "temperature_celsius" from the formatted current weather
    if "temperature_celsius" not in current_weather or current_weather.get("temperature_celsius") is None:
        return {"location": location, "error": "Weather data not available."}

    temp = current_weather.get("temperature_celsius")

    if temp > 35:
        activities = [
            "Stay indoors in an air-conditioned mall",
            "Enjoy a cold smoothie at a trendy cafe",
            "Attend an indoor concert or show"
        ]
    elif temp > 30:
        activities = [
            "Go swimming at a nearby pool or beach",
            "Have an outdoor picnic in the shade",
            "Try water sports or take a boat ride to cool off"
        ]
    elif temp > 25:
        activities = [
            "Take a leisurely walk in the park",
            "Go cycling or rollerblading",
            "Enjoy an iced coffee outdoors"
        ]
    elif temp > 20:
        activities = [
            "Go hiking on a nature trail",
            "Have a light outdoor brunch with friends",
            "Go for a scenic drive"
        ]
    elif temp > 15:
        activities = [
            "Explore a museum or art gallery",
            "Visit a local historical site",
            "Enjoy a quiet afternoon at a cafe"
        ]
    elif temp > 10:
        activities = [
            "Relax at a cozy cafe with a warm drink",
            "Browse a bookstore or library",
            "Watch a movie at a theater"
        ]
    elif temp > 5:
        activities = [
            "Stay indoors and try a new recipe",
            "Play board games with friends or family",
            "Enjoy a warm cup of tea while reading"
        ]
    else:
        activities = [
            "Stay warm indoors and watch a movie marathon",
            "Try crafting or another indoor hobby",
            "Cook a hearty meal and relax at home"
        ]

    return {"location": location, "suggested_activities": activities}


def get_weather_recommendation(user_id):
    """
    Provides a personalized weather-based recommendation for clothing or activities.
    Retrieves the user's location from the database using the UserLocation model.
    If no location is stored, returns an error asking the user to update their location.
    Then, it fetches current weather for that location and returns a recommendation based on the temperature.
    """
    # Retrieve the user's stored location.
    user_loc = UserLocation.query.filter_by(user_id=user_id).first()
    if user_loc is None:
        return {"user_id": user_id, "error": "No location found. Please update your location first."}
    location = user_loc.location

    # Fetch current weather data.
    weather = get_current_weather(location)
    if not weather or "error" in weather:
        return {"user_id": user_id, "location": location, "error": "Weather data not available."}

    current_weather = weather.get("current_weather", {})
    # Try to get the temperature from "temperature_celsius", fall back to "temperature" if needed.
    temp = current_weather.get("temperature_celsius")
    if temp is None:
        temp = current_weather.get("temperature")
    if temp is None:
        return {"user_id": user_id, "location": location, "error": "No current temperature available."}

    # Generate recommendation based on temperature ranges.
    if temp > 35:
        recommendation = "It's extremely hot. Opt for very light clothing, stay hydrated, and avoid prolonged outdoor activities."
    elif temp > 30:
        recommendation = "It's very hot. Wear shorts and a tank top, and consider cooling activities like swimming."
    elif temp > 25:
        recommendation = "It's hot. Choose light clothing and consider outdoor activities such as a picnic or beach visit."
    elif temp > 20:
        recommendation = "It's warm. A light jacket or layers might be comfortable. Enjoy a walk in the park."
    elif temp > 15:
        recommendation = "The weather is moderate. Dress comfortably and enjoy outdoor leisure."
    elif temp > 10:
        recommendation = "It's a bit cool. Consider a sweater and perhaps indoor activities or a quiet stroll."
    elif temp > 5:
        recommendation = "It's chilly. Dress warmly with layers and consider indoor activities."
    else:
        recommendation = "It's extremely cold. Wear heavy clothing and, if possible, stay indoors and keep warm."

    return {"user_id": user_id, "location": location, "recommendation": recommendation}


def get_prediction_confidence(location):
    """
    Computes a rough prediction confidence based on the difference between
    the current temperature and the average forecasted maximum for the next 7 days.
    Returns a dictionary with geocode details at the top and a confidence percentage.
    """
    # Fetch current weather and forecast data.
    current = get_current_weather(location)
    forecast = get_forecast(location)

    if not current or "error" in current:
        return {"error": "Current weather data not available."}
    if not forecast or "error" in forecast:
        return {"error": "Forecast data not available for prediction confidence."}

    # Extract current temperature from the current weather data.
    current_weather = current.get("current_weather", {})
    current_temp = current_weather.get("temperature_celsius") or current_weather.get("temperature")
    if current_temp is None:
        return {"error": "No current temperature available."}
    try:
        current_temp = float(current_temp)
    except Exception:
        return {"error": "Current temperature is not a valid number."}

    # Extract forecast data from the forecast list.
    forecast_list = forecast.get("forecast", [])
    if not forecast_list:
        return {"error": "No forecast data available for prediction confidence."}

    forecast_temps = []
    for day in forecast_list:
        max_temp_str = day.get("max_temp", "")  # e.g., "30.5°C"
        if max_temp_str:
            try:
                temp_val = float(max_temp_str.split("°")[0])
                forecast_temps.append(temp_val)
            except Exception:
                continue
    if not forecast_temps:
        return {"error": "Forecast temperature data unavailable for prediction confidence."}

    forecast_avg = sum(forecast_temps) / len(forecast_temps)
    diff = abs(current_temp - forecast_avg)
    confidence = max(0, 100 - diff * 5)  # Arbitrary formula

    # Use geocode details from current weather data.
    geocode_details = current.get("geocode", {"name": location})

    return {
        "geocode": geocode_details,
        "location": location,
        "confidence": f"{confidence:.0f}%"
    }


def get_historical_weather(location, date_str):
    """
    Fetches historical weather data for a given location and date using Open-Meteo's archive API.
    The 'date_str' should be in YYYY-MM-DD format.
    Returns a dictionary with geocode details at the top and a structured historical weather summary,
    where values are combined with their units.
    """
    geocode_result = geocode_location(location)
    if geocode_result is None:
        return {"error": f"Could not geocode location '{location}'."}
    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_str,
        "end_date": date_str,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        daily = data.get("daily", {})
        units = data.get("daily_units", {})

        # Check if all required fields exist and contain data.
        if not (daily.get("time") and daily.get("temperature_2m_max") and daily.get("temperature_2m_min") and daily.get(
                "precipitation_sum")):
            return {"error": "No historical data available."}

        daily_summary = []
        for i in range(len(daily["time"])):
            day_summary = {
                "date": daily["time"][i],
                "max_temp": f"{daily['temperature_2m_max'][i]} {units.get('temperature_2m_max', '').strip()}",
                "min_temp": f"{daily['temperature_2m_min'][i]} {units.get('temperature_2m_min', '').strip()}",
                "precipitation": f"{daily['precipitation_sum'][i]} {units.get('precipitation_sum', '').strip()}"
            }
            daily_summary.append(day_summary)

        result = {
            "geocode": geocode_details,
            "historical_weather": daily_summary
        }
        return result
    except Exception as e:
        return {"error": str(e)}


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
    Fetches a detailed (hourly) forecast for the next 24 hours using WeatherAPI.com.
    If the API returns a 400 error, it returns a friendly error message.
    """
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": Config.WEATHERAPI_KEY,
        "q": location,
        "days": 3,  # Request forecast for 3 days to ensure sufficient hourly data.
        "aqi": "no",
        "alerts": "no"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Process location data: remove 'localtime_epoch' if it exists.
        location_data = data.get("location", {})
        if "localtime_epoch" in location_data:
            location_data.pop("localtime_epoch")

        # Gather hourly forecast data from all forecast days.
        forecast_days = data.get("forecast", {}).get("forecastday", [])
        hourly_data = []
        for day in forecast_days:
            hourly = day.get("hour", [])
            hourly_data.extend(hourly)
        # Limit the forecast to the next 24 hours.
        hourly_data = hourly_data[:24]

        # Build a more detailed output for each hourly forecast.
        filtered_hourly = []
        for entry in hourly_data:
            filtered_entry = {
                "time": entry.get("time"),
                "temp_c": entry.get("temp_c"),
                "condition": entry.get("condition", {}).get("text"),
                "wind_kph": entry.get("wind_kph"),
                "wind_dir": entry.get("wind_dir"),
                "humidity": entry.get("humidity"),
                "chance_of_rain": entry.get("chance_of_rain"),
            }
            filtered_hourly.append(filtered_entry)

        return {
            "location": location_data,
            "hourly": filtered_hourly
        }
    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 400:
            return {"error": "Location could not be geocoded. Please check your input."}
        else:
            return {"error": str(http_err)}
    except Exception as e:
        return {"error": str(e)}

# Define the acceptable alert types and their descriptions.
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


def subscribe_to_alert(user_id, location, alert_type):
    """
    Persists a subscription for weather alerts.

    Acceptable alert types are:
      1: Extreme heat warning (Temperature >35°C),
      2: High temperature warning (Temperature >30°C),
      3: Low temperature warning (Temperature <5°C),
      4: Extreme low temperature warning (Temperature <15°C),
      5: Strong winds warning (Wind speed >40 km/h),
      6: Extreme winds warning (Wind speed >60 km/h),
      7: Rain and possible thunderstorms detected (if moderate rain),
      8: Heavy rain and thunderstorms detected (if heavy rain).

    Returns a tuple: (success: bool, message: str).
    """
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

    # Check if the subscription already exists.
    existing = Subscription.query.filter_by(user_id=user_id, location=location, alert_type=alert_type).first()
    if existing:
        return (False,
                f"User {user_id} is already subscribed to alert type {alert_type} ({ALERT_TYPES[alert_type]}) for {location}.")

    # Create and store the new subscription.
    subscription = Subscription(user_id=user_id, location=location, alert_type=alert_type)
    db.session.add(subscription)
    try:
        db.session.commit()
        return (
        True, f"User {user_id} subscribed to alert type {alert_type} ({ALERT_TYPES[alert_type]}) for {location}.")
    except Exception as e:
        db.session.rollback()
        return (False, f"An error occurred: {str(e)}")


# @jwt_required()
def cancel_alert():
    """
    Cancels an alert subscription (normal or custom) for the logged-in user.

    Expected JSON for normal alerts:
    {
      "subscription_type": "normal",
      "location": "London",
      "alert_type": "1"   // (as a string)
    }

    Expected JSON for custom alerts:
    {
      "subscription_type": "custom",
      "location": "London",
      "condition": "temperature",         // Must be 'temperature', 'wind_speed', or 'precipitation'
      "operator": ">",                      // Required for temperature and wind_speed
      "threshold": "35"                     // Numeric for temperature/wind_speed or category for precipitation
    }
    """
    data = request.get_json(force=True)
    sub_type = data.get("subscription_type", "").lower().strip()
    location = data.get("location")
    if sub_type not in ["normal", "custom"]:
        return jsonify({"status": "error", "message": "subscription_type must be 'normal' or 'custom'."}), 400
    if not location:
        return jsonify({"status": "error", "message": "Location is required."}), 400

    user_id = get_jwt_identity()

    if sub_type == "normal":
        # For normal alerts, expect an alert_type parameter (as a string)
        alert_type_str = data.get("alert_type")
        if not alert_type_str:
            return jsonify({"status": "error", "message": "For normal subscriptions, 'alert_type' is required."}), 400
        try:
            alert_type_int = int(alert_type_str)
        except ValueError:
            return jsonify({"status": "error", "message": "alert_type must be an integer."}), 400
        subscription = Subscription.query.filter_by(
            user_id=user_id,
            location=location,
            alert_type=alert_type_int
        ).first()
        if subscription:
            db.session.delete(subscription)
            db.session.commit()
            return jsonify({"status": "success",
                            "message": f"Cancelled normal alert type {alert_type_int} ({CUSTOM_ALERT_TYPE.get(alert_type_int, 'Unknown')}) for {location}."}), 200
        else:
            return jsonify({"status": "error",
                            "message": f"No active normal subscription for alert type {alert_type_int} ({CUSTOM_ALERT_TYPE.get(alert_type_int, 'Unknown')}) in {location}."}), 400

    elif sub_type == "custom":
        # For custom alerts, require condition plus the additional fields.
        condition = data.get("condition")
        if not condition:
            return jsonify({"status": "error", "message": "For custom subscriptions, 'condition' is required."}), 400
        cond_lower = condition.lower().strip()
        mapping = {
            "temperature": ALERT_TYPE_TEMP,
            "wind_speed": ALERT_TYPE_WIND,
            "precipitation": ALERT_TYPE_PRECIP
        }
        alert_type = mapping.get(cond_lower)
        if alert_type is None:
            return jsonify({"status": "error",
                            "message": "Condition must be 'temperature', 'wind_speed', or 'precipitation'."}), 400

        # For temperature and wind_speed, require operator and threshold.
        if alert_type in (ALERT_TYPE_TEMP, ALERT_TYPE_WIND):
            operator = data.get("operator")
            threshold = data.get("threshold")
            if not operator or operator.strip() not in (">", "<"):
                return jsonify({"status": "error",
                                "message": "For custom temperature and wind_speed alerts, 'operator' is required and must be '>' or '<'."}), 400
            operator = operator.strip()
            if threshold is None:
                return jsonify({"status": "error",
                                "message": "For custom temperature and wind_speed alerts, 'threshold' is required."}), 400
            try:
                float(threshold)
            except ValueError:
                return jsonify({"status": "error",
                                "message": "For custom temperature and wind_speed alerts, 'threshold' must be numeric."}), 400
        elif alert_type == ALERT_TYPE_PRECIP:
            threshold = data.get("threshold")
            valid_levels = ["no rain", "light", "moderate", "heavy"]
            if not threshold or threshold.lower().strip() not in valid_levels:
                return jsonify({"status": "error",
                                "message": "For custom precipitation alerts, 'threshold' must be one of: no rain, light, moderate, heavy."}), 400
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
            return jsonify({"status": "error",
                            "message": f"A subscription for this custom alert already exists at {location}."}), 400
        custom_sub = CustomSubscription(
            user_id=user_id,
            location=location,
            alert_type=alert_type,
            operator=operator,
            threshold=str(threshold)
        )
        db.session.add(custom_sub)
        db.session.commit()
        return jsonify({"status": "success",
                        "message": f"Cancelled custom alert for {CUSTOM_ALERT_TYPE.get(alert_type, 'Unknown')} at {location} cancelled."}), 200

# Define alert type constants.
ALERT_TYPE_TEMP = 1
ALERT_TYPE_WIND = 2
ALERT_TYPE_PRECIP = 3

# New dictionary for alert type descriptions.
CUSTOM_ALERT_TYPE = {
    ALERT_TYPE_TEMP: "Temperature",
    ALERT_TYPE_WIND: "Wind Speed",
    ALERT_TYPE_PRECIP: "Precipitation Alert"
}

def create_custom_alert(user_id, location, condition, operator=None, threshold=None):
    """
    Creates a custom alert subscription for the logged-in user.
    Returns a tuple: (success: bool, message: str)

    Expected input parameters (all as strings):

    For temperature alerts:
      - condition: "temperature"
      - operator: must be ">" or "<"
      - threshold: numeric value (e.g., "35")
      Example JSON:
      { "location": "London", "condition": "temperature", "operator": ">", "threshold": "35" }

    For wind speed alerts:
      - condition: "wind_speed"
      - operator: must be ">" or "<"
      - threshold: numeric value (e.g., "40")
      Example JSON:
      { "location": "London", "condition": "wind_speed", "operator": ">", "threshold": "40" }

    For precipitation alerts:
      - condition: "precipitation"
      - threshold: one of the following (case-insensitive):
            "no rain", "clear", "cloud", "clouds", "cloudy", "sunny", "light", "moderate", or "heavy"
      (operator is not used)
      Example JSON:
      { "location": "London", "condition": "precipitation", "threshold": "moderate" }
    """
    # Map the condition string to an internal numeric alert type.
    condition_lower = condition.lower().strip() if condition else ""
    mapping = {
        "temperature": ALERT_TYPE_TEMP,
        "wind_speed": ALERT_TYPE_WIND,
        "precipitation": ALERT_TYPE_PRECIP
    }
    alert_type = mapping.get(condition_lower)
    if alert_type is None:
        return False, "Condition must be 'temperature', 'wind_speed', or 'precipitation'."

    # Process based on alert type.
    if alert_type in (ALERT_TYPE_TEMP, ALERT_TYPE_WIND):
        # Require an operator.
        if not operator or operator.strip() not in (">", "<"):
            return False, "Temperature and wind speed alerts require an operator ('>' or '<')."
        operator = operator.strip()
        # Validate that threshold is numeric.
        if threshold is None:
            return False, "Threshold must be provided for temperature and wind speed alerts."
        try:
            float(threshold)
        except (ValueError, TypeError):
            return False, "Threshold must be a numeric value for temperature and wind speed alerts."
    elif alert_type == ALERT_TYPE_PRECIP:
        # Use a dictionary to map various precipitation synonyms.
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
        operator = None  # Not used for precipitation.
        threshold = valid_mapping[threshold.lower().strip()]

    # Check if an identical custom alert already exists.
    existing = CustomSubscription.query.filter_by(
        user_id=user_id,
        location=location,
        alert_type=alert_type,
        operator=operator,
        threshold=str(threshold)
    ).first()
    if existing:
        return False, f"A subscription for this alert already exists at {location}."

    # Create and store the subscription.
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
    """
    Converts a custom alert (stored as JSON) into a human-readable description.
    """
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


def save_user_preferences(user_id, preferences):
    """
    Saves user preferences in the MySQL database.
    If preferences already exist for the user, they are updated.
    """
    user_pref = UserPreference.query.filter_by(user_id=user_id).first()
    if user_pref:
        user_pref.set_preferences(preferences)
    else:
        user_pref = UserPreference(user_id=user_id)
        user_pref.set_preferences(preferences)
        db.session.add(user_pref)
    db.session.commit()
    return f"Preferences for user {user_id} saved."



def get_user_preferences(user_id):
    """
    Retrieves the user's top searched locations and active subscriptions.
    Active subscriptions include normal subscriptions and custom alerts.
    For custom alerts, a human-readable description is generated.
    """
    # Retrieve top searched locations.
    search_history = UserSearchHistory.query.filter_by(user_id=user_id)\
                      .order_by(desc(UserSearchHistory.search_count)).limit(5).all()
    top_locations = [record.location for record in search_history]

    subscriptions = []

    # Normal subscriptions from Subscription table.
    normal_subs = Subscription.query.filter_by(user_id=user_id).all()
    for sub in normal_subs:
        try:
            alert_num = int(sub.alert_type)
            description = ALERT_TYPES.get(alert_num, "Unknown alert")
        except Exception:
            description = "Unknown alert"
        subscriptions.append({
            "location": sub.location,
            "alert_type": sub.alert_type,
            "description": description
        })

    # Custom subscriptions from CustomSubscription table.
    custom_subs = CustomSubscription.query.filter_by(user_id=user_id).all()
    for sub in custom_subs:
        if sub.alert_type == ALERT_TYPE_TEMP:
            description = f"Temperature {sub.operator} {sub.threshold}°C"
        elif sub.alert_type == ALERT_TYPE_WIND:
            description = f"Wind speed {sub.operator} {sub.threshold} km/h"
        elif sub.alert_type == ALERT_TYPE_PRECIP:
            description = f"Precipitation alert: {sub.threshold}"
        else:
            description = "Unknown custom alert"
        subscriptions.append({
            "location": sub.location,
            "alert_type": f"{sub.alert_type} (custom)",
            "description": description
        })

    return {
        "user_id": user_id,
        "top_searches": top_locations,
        "subscriptions": subscriptions
    }

def get_default_location(user_id, provided_location=None):
    """
    Returns the provided_location if available.
    Otherwise, retrieves the user's preferences and returns the top searched location.
    If no preferences exist, returns None.
    """
    if provided_location:
        return provided_location
    prefs = get_user_preferences(user_id)
    top_searches = prefs.get("top_searches", [])
    if top_searches:
        return top_searches[0]
    return None

def update_user_location(user_id, location):
    """
    Updates a user's location in the MySQL database.
    """
    user_loc = UserLocation.query.filter_by(user_id=user_id).first()
    if user_loc:
        user_loc.location = location
    else:
        user_loc = UserLocation(user_id=user_id, location=location)
        db.session.add(user_loc)
    db.session.commit()
    return f"User {user_id}'s location updated to {location}."

def submit_feedback(user_id, rating, comment=""):
   """
   Stores user feedback (a rating between 1 and 5 and an optional comment) in the database.
   Returns a tuple: (success: bool, message: str)
   """
   try:
       rating = int(rating)
   except ValueError:
       return False, "Rating must be an integer."


   if rating < 1 or rating > 5:
       return False, "Rating must be between 1 and 5."


   fb = Feedback(user_id=user_id, rating=rating, comment=comment)
   db.session.add(fb)
   try:
       db.session.commit()
       return True, f"Feedback from user {user_id} recorded."
   except Exception as e:
       db.session.rollback()
       return False, f"An error occurred: {str(e)}"

def map_precipitation_category(description):
    """
    Maps the weather description (from get_current_weather) to one of:
      "no rain", "light", "moderate", or "heavy".

    Mapping is based on keywords in the description:
      - "no rain": if the description contains any of:
          "clear sky", "mainly clear", "partly cloudy", "overcast", "fog", "depositing rime fog"
      - "light": if it contains any of:
          "light drizzle", "light freezing drizzle", "slight rain", "slight rain showers", "slight snow fall", "slight snow showers", "snow grains"
      - "moderate": if it contains any of:
          "moderate drizzle", "moderate rain", "moderate rain showers", "moderate snow fall", "moderate snow showers", "slight or moderate thunderstorm", "thunderstorm with slight hail"
      - "heavy": if it contains any of:
          "dense drizzle", "dense freezing drizzle", "heavy rain", "heavy freezing rain", "heavy snow fall", "heavy rain showers", "heavy snow showers", "thunderstorm with heavy hail"

    If no keywords match, returns "unknown".
    """
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
    """
    Evaluates a normal alert subscription based on current weather data.
    Uses fixed thresholds from ALERT_TYPES.
    """
    cw = weather.get("current_weather", {})
    if not cw:
        return None

    temp = cw.get("temperature_celsius")
    wind = cw.get("wind_speed_kph")
    desc = cw.get("weather_description", "").lower()
    alert_type = subscription.alert_type

    if alert_type == "1":  # Extreme heat warning: Temperature >35°C
        if temp is not None and temp > 35:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, exceeding 35°C."
    elif alert_type == "2":  # High temperature warning: Temperature >30°C
        if temp is not None and temp > 30:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, exceeding 30°C."
    elif alert_type == "3":  # Low temperature warning: Temperature <5°C
        if temp is not None and temp < 5:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, below 5°C."
    elif alert_type == "4":  # Extreme low temperature warning: Temperature <15°C
        if temp is not None and temp < 15:
            return f"Alert: Temperature at {subscription.location} is {temp}°C, below 15°C."
    elif alert_type == "5":  # Strong winds warning: Wind speed >40 km/h
        if wind is not None and wind > 40:
            return f"Alert: Wind speed at {subscription.location} is {wind} km/h, exceeding 40 km/h."
    elif alert_type == "6":  # Extreme winds warning: Wind speed >60 km/h
        if wind is not None and wind > 60:
            return f"Alert: Wind speed at {subscription.location} is {wind} km/h, exceeding 60 km/h."
    elif alert_type == "7":  # Moderate rain alert: mapped precipitation category equals "moderate"
        current_category = map_precipitation_category(cw.get("weather_description", ""))
        if current_category == "moderate":
            return f"Alert: Precipitation at {subscription.location} is moderate."
    elif alert_type == "8":  # Heavy rain alert: mapped precipitation category equals "heavy"
        current_category = map_precipitation_category(cw.get("weather_description", ""))
        if current_category == "heavy":
            return f"Alert: Heavy rain detected at {subscription.location}."
    return None

def evaluate_custom_alert(subscription, weather):
    """
    Evaluates a custom alert subscription using current weather data.
    For temperature and wind_speed custom alerts, compares the current value
    against the stored threshold using the stored operator.
    For precipitation custom alerts, maps the weather description to a category
    and triggers an alert if the current category matches the subscribed category.
    """
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
        # Trigger an alert if the current category matches the subscription threshold.
        if current_category == subscribed_category:
            return f"Precipitation at {subscription.location} is '{current_category}'."
    return None
