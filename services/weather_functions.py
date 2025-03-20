import requests
import difflib
from config import Config
from models import UserLocation
from datetime import timedelta, date
from user_functions import log_user_search

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

def split_locations(value):
    """
    Splits the input string on commas and returns a list of trimmed location names.
    For example, "London, Paris, Tokyo" becomes ["London", "Paris", "Tokyo"].
    """
    return [loc.strip() for loc in value.split(',') if loc.strip()]

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