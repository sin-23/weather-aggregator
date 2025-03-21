import requests
import difflib
from config import Config
from models import UserLocation
from datetime import timedelta, date
from services.user_functions import log_user_search

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
        threshold = 0.65
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
                if query_norm in norm_field:
                    lat = float(candidate.get("lat"))
                    lon = float(candidate.get("lon"))
                    name = address.get("city") or address.get("town") or address.get("village") or address.get("locality") or candidate.get("display_name")
                    region = address.get("state") or address.get("county")
                    country = address.get("country")
                    return {"lat": lat, "lon": lon, "name": name, "region": region, "country": country}
                else:
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
    geocode_result = geocode_location(location)
    if geocode_result is None:
        return {"error": f"Could not geocode location '{location}'."}

    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    if start_date is None:
        start_date_obj = date.today()
    else:
        try:
            start_date_obj = date.fromisoformat(start_date)
        except ValueError:
            return {"error": "Invalid start_date format. Use YYYY-MM-DD."}

    end_date = (start_date_obj + timedelta(days=6)).isoformat()
    start_date = start_date_obj.isoformat()

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

        result = {
            "geocode": geocode_details,
            "forecast": daily_data
        }
        return result

    except Exception as e:
        return {"error": str(e)}


def get_forecast_with_date(location, start_date):
    try:
        start_date_obj = date.fromisoformat(start_date)
    except ValueError:
        return {"error": "Invalid start_date format. Use YYYY-MM-DD."}

    max_forecast_date = date.today() + timedelta(days=7)
    if start_date_obj > max_forecast_date:
        return {"error": "start_date is too far in the future. Please choose a date within the next 7 days."}

    return get_forecast(location, start_date)

def split_locations(value):
    return [loc.strip() for loc in value.split(',') if loc.strip()]

def compare_weather(locations):
    results = {}
    for loc in locations:
        weather = get_current_weather(loc)
        if "error" in weather:
            results[loc] = {"error": weather["error"]}
        else:
            results[loc] = weather
    return results

def get_climate_data(region):
    geocode_result = geocode_location(region)
    if geocode_result is None:
        return {"error": f"Could not geocode region '{region}'."}

    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    end_date = date.today() - timedelta(days=1)
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
        rows = table.find_all("tr")[1:]
        for row in rows:
            if len(trending) >= 5:
                break
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            candidate = cells[1].get_text(strip=True)
            if "List of" in candidate:
                continue

            normalized_candidate = candidate.lower().strip()

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
    trending_cities = get_trending_cities()
    if not trending_cities:
        trending_cities = ["Chicago", "London", "Tokyo", "Sydney", "Paris"]
    results = {}
    for city in trending_cities:
        results[city] = get_current_weather(city)
    return {"trending_weather": results}

def get_seasonal_changes(region):
    geocode_result = geocode_location(region)
    if geocode_result is None:
        return {"error": f"Could not geocode region '{region}'."}
    lat, lon = geocode_result["lat"], geocode_result["lon"]
    geocode_details = {
        "name": geocode_result.get("name", "Unknown"),
        "region": geocode_result.get("region", "Unknown"),
        "country": geocode_result.get("country", "Unknown")
    }

    current = get_current_weather(region)
    if not current or "error" in current:
        return {"error": "No current weather data available."}

    current_temp = current.get("current_weather", {}).get("temperature_celsius")
    if current_temp is None:
        return {"error": "No current temperature available."}

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
    weather = get_current_weather(location)
    if not weather or "error" in weather:
        return {"location": location, "error": "Weather data not available."}

    current_weather = weather.get("current_weather", {})
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
    user_loc = UserLocation.query.filter_by(user_id=user_id).first()
    if user_loc is None:
        return {"user_id": user_id, "error": "No location found. Please update your location first."}
    location = user_loc.location

    weather = get_current_weather(location)
    if not weather or "error" in weather:
        return {"user_id": user_id, "location": location, "error": "Weather data not available."}

    current_weather = weather.get("current_weather", {})
    temp = current_weather.get("temperature_celsius")
    if temp is None:
        temp = current_weather.get("temperature")
    if temp is None:
        return {"user_id": user_id, "location": location, "error": "No current temperature available."}

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
    current = get_current_weather(location)
    forecast = get_forecast(location)

    if not current or "error" in current:
        return {"error": "Current weather data not available."}
    if not forecast or "error" in forecast:
        return {"error": "Forecast data not available for prediction confidence."}

    current_weather = current.get("current_weather", {})
    current_temp = current_weather.get("temperature_celsius") or current_weather.get("temperature")
    if current_temp is None:
        return {"error": "No current temperature available."}
    try:
        current_temp = float(current_temp)
    except Exception:
        return {"error": "Current temperature is not a valid number."}

    forecast_list = forecast.get("forecast", [])
    if not forecast_list:
        return {"error": "No forecast data available for prediction confidence."}

    forecast_temps = []
    for day in forecast_list:
        max_temp_str = day.get("max_temp", "")
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
    confidence = max(0, 100 - diff * 5)

    geocode_details = current.get("geocode", {"name": location})

    return {
        "geocode": geocode_details,
        "location": location,
        "confidence": f"{confidence:.0f}%"
    }

def get_historical_weather(location, date_str):
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
    data = get_current_weather(location)
    if "error" in data:
        return data

    current = data.get("current_weather", {})

    current["humidity"] = 60
    current["pressure"] = 1013
    current["visibility"] = 10

    data["current_weather"] = current
    return data

def get_detailed_forecast(location):
    url = "http://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": Config.WEATHERAPI_KEY,
        "q": location,
        "days": 3,
        "aqi": "no",
        "alerts": "no"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        location_data = data.get("location", {})
        if "localtime_epoch" in location_data:
            location_data.pop("localtime_epoch")

        forecast_days = data.get("forecast", {}).get("forecastday", [])
        hourly_data = []
        for day in forecast_days:
            hourly = day.get("hour", [])
            hourly_data.extend(hourly)
        hourly_data = hourly_data[:24]

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