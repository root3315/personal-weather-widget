#!/usr/bin/env python3
"""
Personal Weather Widget - Self-hosted lightweight weather dashboard.
Fetches current weather and forecast data, renders an HTML widget.
"""

import os
import json
import time
import hashlib
import urllib.request
import urllib.parse
import argparse
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import Lock

CACHE_DIR = Path(os.environ.get("WEATHER_CACHE_DIR", "/tmp/weather_widget"))
CACHE_TTL = int(os.environ.get("WEATHER_CACHE_TTL", "600"))
DEFAULT_LOCATIONS = os.environ.get("WEATHER_LOCATIONS", "London,New York,Tokyo")
DEFAULT_UNITS = os.environ.get("WEATHER_UNITS", "metric")
HOST = os.environ.get("WEATHER_HOST", "0.0.0.0")
PORT = int(os.environ.get("WEATHER_PORT", "8090"))
REFRESH_INTERVAL = int(os.environ.get("WEATHER_REFRESH", "300"))

data_lock = Lock()
weather_cache = {}


def build_openweathermap_url(location, api_key, units="metric"):
    """Construct the OpenWeatherMap API request URL."""
    base = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": api_key,
        "units": units,
    }
    query = urllib.parse.urlencode(params)
    return f"{base}?{query}"


def build_forecast_url(location, api_key, units="metric"):
    """Construct the 5-day forecast API request URL."""
    base = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": location,
        "appid": api_key,
        "units": units,
    }
    query = urllib.parse.urlencode(params)
    return f"{base}?{query}"


def fetch_json(url, timeout=10):
    """Perform an HTTP GET request and return parsed JSON."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "PersonalWeatherWidget/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def cache_key_for(location):
    """Generate a deterministic cache key from a location string."""
    return hashlib.sha256(location.strip().lower().encode()).hexdigest()[:12]


def get_cached(location):
    """Retrieve data from the in-memory cache if it is still valid."""
    key = cache_key_for(location)
    if key in weather_cache:
        entry = weather_cache[key]
        age = time.time() - entry["timestamp"]
        if age < CACHE_TTL:
            return entry["data"]
    return None


def set_cached(location, data):
    """Store data in the in-memory cache with the current timestamp."""
    key = cache_key_for(location)
    weather_cache[key] = {
        "data": data,
        "timestamp": time.time(),
        "location": location,
    }


def fetch_weather(location, api_key, units="metric"):
    """Fetch current weather for a location, using cache when possible."""
    cached = get_cached(location)
    if cached is not None:
        return cached

    url = build_openweathermap_url(location, api_key, units)
    try:
        data = fetch_json(url)
        if data.get("cod") != 200:
            return {"error": data.get("message", "Unknown error"), "location": location}
        set_cached(location, data)
        return data
    except Exception as exc:
        return {"error": str(exc), "location": location}


def fetch_forecast(location, api_key, units="metric"):
    """Fetch 5-day / 3-hour forecast and return a simplified list."""
    url = build_forecast_url(location, api_key, units)
    try:
        data = fetch_json(url)
        if data.get("cod") != "200":
            return []
        items = []
        for entry in data.get("list", [])[:8]:
            dt = datetime.fromtimestamp(entry["dt"], tz=timezone.utc)
            items.append({
                "time": dt.strftime("%H:%M"),
                "temp": entry["main"]["temp"],
                "icon": entry["weather"][0]["icon"],
                "description": entry["weather"][0]["description"],
                "wind_speed": entry["wind"]["speed"],
            })
        return items
    except Exception:
        return []


def format_temp(temp, units):
    """Format a temperature value with the correct unit symbol."""
    if units == "metric":
        return f"{temp:.1f}°C"
    elif units == "imperial":
        return f"{temp:.1f}°F"
    return f"{temp:.1f}°K"


def wind_label(speed, units):
    """Return a human-readable wind speed string."""
    if units == "metric":
        return f"{speed:.1f} m/s"
    elif units == "imperial":
        return f"{speed:.1f} mph"
    return f"{speed:.1f} m/s"


def icon_url(icon_code):
    """Return the OpenWeatherMap icon URL."""
    return f"https://openweathermap.org/img/wn/{icon_code}.png"


def render_widget(locations_data, units):
    """Build the full HTML page with embedded CSS and weather cards."""
    unit_label = "°C" if units == "metric" else ("°F" if units == "imperial" else "K")
    cards_html = ""
    for entry in locations_data:
        data = entry["current"]
        forecast = entry["forecast"]
        if "error" in data:
            cards_html += f"""
            <div class="card card-error">
                <h2>{data.get('location', 'Unknown')}</h2>
                <p class="error-msg">{data['error']}</p>
            </div>"""
            continue

        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = data.get("weather", [{}])[0]
        name = data.get("name", entry["location"])
        temp = format_temp(main.get("temp", 0), units)
        feels_like = format_temp(main.get("feels_like", 0), units)
        humidity = main.get("humidity", 0)
        pressure = main.get("pressure", 0)
        wind_spd = wind_label(wind.get("speed", 0), units)
        desc = weather.get("description", "").capitalize()
        icon = weather.get("icon", "01d")
        updated = datetime.now().strftime("%H:%M:%S")

        forecast_html = ""
        for fc in forecast:
            forecast_html += f"""
            <div class="forecast-item">
                <span class="fc-time">{fc['time']}</span>
                <img src="{icon_url(fc['icon'])}" alt="" class="fc-icon">
                <span class="fc-temp">{format_temp(fc['temp'], units)}</span>
            </div>"""

        cards_html += f"""
        <div class="card">
            <div class="card-header">
                <h2>{name}</h2>
                <span class="updated">Updated: {updated}</span>
            </div>
            <div class="card-body">
                <div class="main-weather">
                    <img src="{icon_url(icon)}" alt="{desc}" class="weather-icon">
                    <div class="temp-display">{temp}</div>
                </div>
                <p class="description">{desc}</p>
                <div class="details-grid">
                    <div class="detail"><span>Feels like</span><strong>{feels_like}</strong></div>
                    <div class="detail"><span>Humidity</span><strong>{humidity}%</strong></div>
                    <div class="detail"><span>Pressure</span><strong>{pressure} hPa</strong></div>
                    <div class="detail"><span>Wind</span><strong>{wind_spd}</strong></div>
                </div>
            </div>
            {f'<div class="forecast"><h3>Forecast</h3><div class="forecast-row">{forecast_html}</div></div>' if forecast else ''}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Weather Widget</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 2rem;
        }}
        h1 {{ text-align: center; margin-bottom: 2rem; font-weight: 300; color: #fff; }}
        .container {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 1.5rem;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .card {{
            background: rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            overflow: hidden;
            transition: transform 0.2s;
        }}
        .card:hover {{ transform: translateY(-4px); }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.25rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .card-header h2 {{ font-size: 1.25rem; font-weight: 500; }}
        .updated {{ font-size: 0.75rem; opacity: 0.6; }}
        .card-body {{ padding: 1.25rem; }}
        .main-weather {{ display: flex; align-items: center; gap: 1rem; }}
        .weather-icon {{ width: 80px; height: 80px; }}
        .temp-display {{ font-size: 2.5rem; font-weight: 700; }}
        .description {{ text-transform: capitalize; margin: 0.5rem 0 1rem; opacity: 0.8; }}
        .details-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.75rem;
        }}
        .detail {{
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            padding: 0.4rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}
        .detail strong {{ font-weight: 600; }}
        .forecast {{
            padding: 0 1.25rem 1.25rem;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .forecast h3 {{ font-size: 0.9rem; margin: 0.75rem 0 0.5rem; opacity: 0.7; }}
        .forecast-row {{ display: flex; gap: 0.5rem; overflow-x: auto; padding-bottom: 0.5rem; }}
        .forecast-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 0.5rem;
            min-width: 70px;
            font-size: 0.8rem;
        }}
        .fc-icon {{ width: 40px; height: 40px; }}
        .card-error {{ border-left: 4px solid #e74c3c; }}
        .error-msg {{ color: #e74c3c; padding: 1rem; }}
        .meta {{
            text-align: center;
            margin-top: 2rem;
            font-size: 0.8rem;
            opacity: 0.4;
        }}
    </style>
</head>
<body>
    <h1>Weather Dashboard</h1>
    <div class="container">{cards_html}</div>
    <div class="meta">Auto-refreshes every {REFRESH_INTERVAL}s | Units: {unit_label}</div>
    <script>
        setTimeout(() => location.reload(), {REFRESH_INTERVAL * 1000});
    </script>
</body>
</html>"""
    return html


def collect_all_weather(api_key, locations, units):
    """Fetch weather data for all locations and return structured results."""
    results = []
    for loc in locations:
        loc = loc.strip()
        if not loc:
            continue
        current = fetch_weather(loc, api_key, units)
        forecast = fetch_forecast(loc, api_key, units) if "error" not in current else []
        results.append({"location": loc, "current": current, "forecast": forecast})
    return results


def run_server(api_key, locations, units):
    """Start the built-in HTTP server that serves the weather widget."""
    locations_list = [l.strip() for l in locations.split(",") if l.strip()]
    if not locations_list:
        locations_list = [l.strip() for l in DEFAULT_LOCATIONS.split(",")]

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    class WeatherHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                with data_lock:
                    data = collect_all_weather(api_key, locations_list, units)
                html = render_widget(data, units)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
            elif self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            elif self.path == "/api/weather":
                with data_lock:
                    data = collect_all_weather(api_key, locations_list, units)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not Found")

        def log_message(self, fmt, *args):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{ts}] {fmt % args}")

    server = HTTPServer((HOST, PORT), WeatherHandler)
    print(f"Personal Weather Widget running on http://{HOST}:{PORT}")
    print(f"Monitoring: {', '.join(locations_list)}")
    print(f"Units: {units} | Cache TTL: {CACHE_TTL}s")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


def main():
    """Entry point: parse arguments and launch the server."""
    parser = argparse.ArgumentParser(description="Personal Weather Widget")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENWEATHER_API_KEY", ""),
        help="OpenWeatherMap API key",
    )
    parser.add_argument(
        "--locations",
        default=DEFAULT_LOCATIONS,
        help="Comma-separated list of cities",
    )
    parser.add_argument(
        "--units",
        choices=["metric", "imperial", "standard"],
        default=DEFAULT_UNITS,
        help="Temperature units",
    )
    parser.add_argument("--host", default=HOST, help="Bind address")
    parser.add_argument("--port", type=int, default=PORT, help="Bind port")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: Set OPENWEATHER_API_KEY env var or pass --api-key")
        raise SystemExit(1)

    global HOST, PORT
    HOST = args.host
    PORT = args.port

    run_server(args.api_key, args.locations, args.units)


if __name__ == "__main__":
    main()
