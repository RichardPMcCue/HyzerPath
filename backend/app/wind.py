import logging
import httpx
from typing import Optional

logger = logging.getLogger("hyzerpath.wind")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


async def get_wind(latitude: float, longitude: float) -> Optional[dict]:
    """Fetches current wind at a location from Open-Meteo (free, no API key).

    Returns {"speed": mph, "direction": degrees} where direction is the
    meteorological convention (the direction the wind is blowing FROM),
    or None if the request fails."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "wind_speed_10m,wind_direction_10m",
        "wind_speed_unit": "mph",
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(OPEN_METEO_URL, params=params, timeout=10)
            response.raise_for_status()
            current = response.json()["current"]
            return {
                "speed": float(current["wind_speed_10m"]),
                "direction": float(current["wind_direction_10m"]),
            }
    except Exception as e:
        logger.warning("wind lookup failed", extra={"error": str(e)})
        return None
