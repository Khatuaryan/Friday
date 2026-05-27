"""
Web Search & Weather Tools — Interfaces with DuckDuckGo for searches and wttr.in for weather.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List
from urllib.parse import unquote

import httpx

from .base import Tool

logger = logging.getLogger("friday.tools.web")


class WebSearchTool(Tool):
    """Searches the web via DuckDuckGo HTML search cleanly without heavy external parsers."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for up-to-date information, news, or general knowledge using DuckDuckGo"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string",
                },
            },
            "required": ["query"],
        }

    def execute(self, query: str) -> Dict[str, Any]:
        query = query.strip()
        if not query:
            return {"error": "Query cannot be empty"}

        logger.info("Executing web search for: %s", query)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            # Step 1: Try DDG Instant Answer API first for fast, clean details
            api_url = f"https://api.duckduckgo.com/?q={query}&format=json"
            response = httpx.get(api_url, headers=headers, timeout=10.0, follow_redirects=True)
            if response.status_code == 200:
                try:
                    data = response.json()
                    abstract = data.get("AbstractText", "")
                    if abstract:
                        return {
                            "query": query,
                            "source": "DuckDuckGo Instant Answer",
                            "abstract": abstract,
                            "results": [{"title": data.get("Heading", query), "url": data.get("AbstractURL", ""), "snippet": abstract}]
                        }
                except Exception:
                    pass

            # Step 2: Fall back to HTML search for general web results
            html_url = f"https://html.duckduckgo.com/html/?q={query}"
            html_response = httpx.get(html_url, headers=headers, timeout=10.0, follow_redirects=True)
            if html_response.status_code != 200:
                return {"error": f"Search failed with HTTP status {html_response.status_code}"}

            html = html_response.text
            results = self._parse_ddg_html(html)

            if not results:
                return {
                    "query": query,
                    "message": "No search results were found for this query.",
                    "results": []
                }

            return {
                "query": query,
                "source": "DuckDuckGo HTML",
                "results": results[:5]  # Top 5 results
            }

        except httpx.RequestError as e:
            logger.error("Web search request failed: %s", e)
            return {"error": f"Network request failed: {e}"}
        except Exception as e:
            logger.error("Failed executing search: %s", e)
            return {"error": str(e)}

    def _parse_ddg_html(self, html: str) -> List[Dict[str, str]]:
        """Extract results using lightweight regex matching class attributes."""
        # Find result containers
        blocks = re.findall(r'<div class="[^"]*result[^"]*"[^>]*>.*?</div>\s*</div>', html, re.DOTALL)
        if not blocks:
            # Simpler fallback match for older or alternative DDG structures
            blocks = re.findall(r'<div class="result body[^"]*">.*?</div>\s*</div>', html, re.DOTALL)

        results = []
        for block in blocks:
            # Extract URL and Title
            a_match = re.search(r'<a class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL)
            # Extract Snippet description
            snippet_match = re.search(r'<a class="result__snippet"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not snippet_match:
                snippet_match = re.search(r'<div class="result__snippet"[^>]*>(.*?)</div>', block, re.DOTALL)

            if a_match:
                raw_url = a_match.group(1)
                
                # Resolve uddg redirect wrapper
                url = raw_url
                if "uddg=" in raw_url:
                    try:
                        url_part = raw_url.split("uddg=")[1].split("&")[0]
                        url = unquote(url_part)
                    except Exception:
                        pass
                
                # Strip HTML tags from title and snippet
                title = re.sub(r'<[^>]+>', '', a_match.group(2)).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
                
                # Unescape standard HTML characters
                title = self._unescape_html(title)
                snippet = self._unescape_html(snippet)

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet
                })
        return results

    def _unescape_html(self, text: str) -> str:
        replacements = {
            "&quot;": '"',
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&#x27;": "'",
            "&#39;": "'",
            "&nbsp;": " "
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text


class WeatherTool(Tool):
    """Retrieves current weather details via wttr.in JSON API."""

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Retrieve the current weather and forecasts for a specific city or region"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City or region name (default: 'Mumbai')",
                    "default": "Mumbai",
                },
            },
        }

    def execute(self, location: str = "Mumbai") -> Dict[str, Any]:
        location = location.strip() if location else "Mumbai"
        logger.info("Retrieving weather for location: %s", location)

        url = f"https://wttr.in/{location}?format=j1"
        try:
            response = httpx.get(url, timeout=10.0, follow_redirects=True)
            if response.status_code != 200:
                return {"error": f"wttr.in request failed with status code {response.status_code}"}

            data = response.json()
            current = data.get("current_condition", [{}])[0]
            nearest_area = data.get("nearest_area", [{}])[0]

            temp_c = current.get("temp_C", "N/A")
            feels_like_c = current.get("FeelsLikeC", "N/A")
            humidity = current.get("humidity", "N/A")
            weather_desc = current.get("weatherDesc", [{}])[0].get("value", "N/A")
            wind_speed = current.get("windspeedKmph", "N/A")

            city = nearest_area.get("areaName", [{}])[0].get("value", location)
            country = nearest_area.get("country", [{}])[0].get("value", "N/A")

            # Extract 1-day forecast details
            forecast = data.get("weather", [{}])[0]
            max_temp = forecast.get("maxtempC", "N/A")
            min_temp = forecast.get("mintempC", "N/A")

            return {
                "location": f"{city}, {country}",
                "temperature_celsius": temp_c,
                "feels_like_celsius": feels_like_c,
                "condition": weather_desc,
                "humidity_percent": humidity,
                "wind_speed_kmh": wind_speed,
                "forecast_today": {
                    "max_celsius": max_temp,
                    "min_celsius": min_temp
                }
            }

        except httpx.RequestError as e:
            logger.error("wttr.in request failed: %s", e)
            return {"error": f"Network request failed: {e}"}
        except Exception as e:
            logger.error("Failed to parse weather data: %s", e)
            return {"error": str(e)}
