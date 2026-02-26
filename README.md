# Personal Weather Widget

A lightweight, self-hosted weather dashboard built with Python. Monitor current conditions and forecasts for multiple cities with a clean, responsive interface.

## Features

- Real-time weather for multiple locations
- 5-day forecast with 3-hour intervals
- In-memory caching to respect API rate limits
- Responsive glassmorphism UI
- JSON API endpoint at `/api/weather`
- Health check at `/health`
- Configurable units (metric, imperial, standard)
- Auto-refreshing page

## Prerequisites

- Python 3.7+
- An OpenWeatherMap API key (free tier works) — get one at https://openweathermap.org/api

## Quick Start

```bash
export OPENWEATHER_API_KEY="your-api-key-here"
python weather_widget.py
```

Open http://localhost:8090 in your browser.

## Configuration

### Command-line arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--api-key` | `$OPENWEATHER_API_KEY` | OpenWeatherMap API key |
| `--locations` | `London,New York,Tokyo` | Comma-separated city names |
| `--units` | `metric` | `metric`, `imperial`, or `standard` |
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8090` | Bind port |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENWEATHER_API_KEY` | *(empty)* | Required API key |
| `WEATHER_LOCATIONS` | `London,New York,Tokyo` | Default cities |
| `WEATHER_UNITS` | `metric` | Temperature units |
| `WEATHER_HOST` | `0.0.0.0` | Bind address |
| `WEATHER_PORT` | `8090` | Bind port |
| `WEATHER_CACHE_TTL` | `600` | Cache lifetime in seconds |
| `WEATHER_REFRESH` | `300` | Page auto-refresh interval |
| `WEATHER_CACHE_DIR` | `/tmp/weather_widget` | Cache directory path |

### Examples

```bash
# Monitor US cities in Fahrenheit
python weather_widget.py --locations "Chicago,Los Angeles,Miami" --units imperial --port 9000

# Custom host and locations
python weather_widget.py --locations "Paris,Berlin,Rome" --host 127.0.0.1 --port 3000
```

## Endpoints

| Path | Content |
|------|---------|
| `/` | HTML weather dashboard |
| `/health` | Plain text `OK` |
| `/api/weather` | JSON response with all location data |

## Deployment

### Systemd service

Create `/etc/systemd/system/weather-widget.service`:

```ini
[Unit]
Description=Personal Weather Widget
After=network.target

[Service]
Type=simple
Environment=OPENWEATHER_API_KEY=your-key
Environment=WEATHER_LOCATIONS=London,New York,Tokyo
ExecStart=/usr/bin/python3 /opt/weather-widget/weather_widget.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
systemctl enable --now weather-widget
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY weather_widget.py .
EXPOSE 8090
CMD ["python", "weather_widget.py"]
```

```bash
docker build -t weather-widget .
docker run -d -p 8090:8090 -e OPENWEATHER_API_KEY=your-key weather-widget
```

### Nginx reverse proxy

```nginx
server {
    listen 80;
    server_name weather.example.com;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Project Structure

```
weather_widget.py   — Main application (server + logic)
README.md           — This file
requirements.txt    — Python dependencies (none required)
```

## License

MIT
