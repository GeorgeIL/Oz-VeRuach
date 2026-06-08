import os
import logging
import json
import re
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional
from http import HTTPStatus
from datetime import datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
_BEDROCK_KB_ID = os.environ.get("BEDROCK_KB_ID", "")
_METEOSOURCE_API_KEY = os.environ.get("METEOSOURCE_API_KEY", "")
_FLASK_TOOL_URL = os.environ.get(
    "FLASK_TOOL_URL", "http://127.0.0.1:5000/chat/agent/share-recipe"
)
_AGENT_TOOL_SECRET = os.environ.get("AGENT_TOOL_SECRET", "")

_RECIPE_KEYWORDS = (
    "recipe",
    "cook",
    "dish",
    "meal",
    "suggest",
    "recommend",
    "dinner",
    "lunch",
    "breakfast",
    "brunch",
    "supper",
    "eat",
    "food",
    "make for",
)

_bedrock_agent_runtime = None


def _agent_runtime():
    global _bedrock_agent_runtime
    if _bedrock_agent_runtime is None:
        _bedrock_agent_runtime = boto3.client(
            "bedrock-agent-runtime", region_name=_AWS_REGION
        )
    return _bedrock_agent_runtime


def _param_value(event: Dict[str, Any], name: str) -> Optional[str]:
    for param in event.get("parameters", []):
        if param.get("name", "").lower() == name.lower():
            return param.get("value")
    return None


def _input_text(event: Dict[str, Any]) -> str:
    return str(event.get("inputText") or "").strip()


def _normalize_place_id(location: str) -> str:
    return location.strip().lower().replace(" ", "-")


def _wants_recipe_suggestion(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in _RECIPE_KEYWORDS)


_LOCATION_STOPWORDS = {
    "the",
    "a",
    "an",
    "my",
    "this",
    "that",
    "current",
    "today",
    "now",
    "me",
    "you",
    "right",
}


def _resolve_location(event: Dict[str, Any]) -> Optional[str]:
    param_location = _param_value(event, "location")
    if param_location:
        return _normalize_place_id(param_location)

    text = _input_text(event)
    if not text:
        return None

    in_matches = re.findall(
        r"\bin\s+([A-Za-z][A-Za-z\s\-]{1,40}?)(?:\?|\.|,|$|\s+(?:right\s+now|currently|today|weather|time))",
        text,
        re.IGNORECASE,
    )
    for place in reversed(in_matches):
        cleaned = place.strip()
        if cleaned.lower() not in _LOCATION_STOPWORDS:
            return _normalize_place_id(cleaned)

    for_match = re.search(
        r"\bfor\s+([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)*)(?:\?|\.|,|$|\s)",
        text,
    )
    if for_match:
        return _normalize_place_id(for_match.group(1))

    fallback_patterns = [
        r"\b([A-Za-z][A-Za-z\s\-]{0,40}?)\s+weather\b",
        r"\bweather\s+in\s+([A-Za-z][A-Za-z\s\-]{0,40}?)(?:\?|\.|,|$)",
    ]
    for pattern in fallback_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            place = match.group(1).strip()
            if place.lower() not in _LOCATION_STOPWORDS:
                return _normalize_place_id(place)
    return None


def _meal_period(hour: int) -> tuple[str, str]:
    if hour < 11:
        return "morning", "breakfast"
    if hour < 16:
        return "afternoon", "lunch"
    return "evening", "dinner"


def _fetch_weather(location: str) -> tuple[str, str]:
    if not _METEOSOURCE_API_KEY:
        raise ValueError("METEOSOURCE_API_KEY is not configured")

    url = "https://www.meteosource.com/api/v1/free/point"
    params = {
        "place_id": location,
        "sections": "current",
        "timezone": "UTC",
        "language": "en",
        "units": "metric",
        "key": _METEOSOURCE_API_KEY,
    }
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"

    req = urllib.request.Request(full_url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as api_response:
        if api_response.status != 200:
            raise Exception(f"Weather API failed with status: {api_response.status}")

        weather_data = json.loads(api_response.read().decode("utf-8"))
        current = weather_data.get("current", {})
        temp = current.get("temperature", "unknown")
        summary = current.get("summary", "no data")
        return str(summary), str(temp)


def _extract_titles(chunks: list[str], limit: int = 3) -> list[str]:
    titles: list[str] = []
    for chunk in chunks:
        match = re.search(r"^#\s+(.+)$", chunk.strip(), re.MULTILINE)
        if match:
            title = match.group(1).strip()
            if title and title not in titles:
                titles.append(title)
        if len(titles) >= limit:
            break
    return titles


def _retrieve_recipe_suggestions(query: str, top_k: int = 5) -> list[str]:
    if not _BEDROCK_KB_ID:
        return []

    try:
        response = _agent_runtime().retrieve(
            knowledgeBaseId=_BEDROCK_KB_ID,
            retrievalQuery={"text": query},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": top_k}
            },
        )
    except Exception as exc:
        logger.error("Knowledge base retrieve failed: %s", exc)
        return []

    return [
        r.get("content", {}).get("text", "").strip()
        for r in response.get("retrievalResults", [])
        if r.get("content", {}).get("text", "").strip()
    ]


def _get_time_text() -> str:
    now = datetime.now()
    return f"The current date and time is {now.strftime('%Y-%m-%d %H:%M:%S')}"


def _get_weather_text(location: str) -> str:
    summary, temp = _fetch_weather(location)
    return f"The weather in {location} is {summary} with temperature {temp}°C."


def _suggest_dish_for_time_and_weather(event: Dict[str, Any]) -> str:
    location = _resolve_location(event)
    meal_hint = (_param_value(event, "meal_hint") or "").strip()

    if not location:
        raise ValueError(
            "Location is required. Pass a location parameter or mention a city "
            "(e.g. 'recipe for Paris')."
        )

    now = datetime.now()
    period_name, meal_type = _meal_period(now.hour)
    summary, temp = _fetch_weather(location)

    query_parts = [
        "recipes for",
        summary,
        f"{temp}C",
        period_name,
        meal_type,
        meal_hint,
    ]
    retrieval_query = " ".join(part for part in query_parts if part)
    chunks = _retrieve_recipe_suggestions(retrieval_query)
    titles = _extract_titles(chunks)

    lines = [
        f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Meal period: {period_name} ({meal_type})",
        f"Weather in {location}: {summary}, {temp}°C.",
    ]
    if meal_hint:
        lines.append(f"Meal preference: {meal_hint}.")

    if titles:
        lines.append("Suggested cookbook recipes:")
        for idx, title in enumerate(titles, start=1):
            lines.append(f"{idx}. {title} — fits current time and weather.")
    elif chunks:
        lines.append("Relevant cookbook excerpts (use titles from context):")
        for idx, chunk in enumerate(chunks[:3], start=1):
            snippet = chunk[:300].replace("\n", " ")
            lines.append(f"{idx}. {snippet}...")
    else:
        lines.append(
            "No matching recipes found in the knowledge base for this context."
        )

    return "\n".join(lines)


def _handle_get_time(event: Dict[str, Any]) -> str:
    text = _input_text(event)
    location = _resolve_location(event)
    wants_recipe = _wants_recipe_suggestion(text) or bool(_param_value(event, "meal_hint"))

    if wants_recipe or location:
        if location and _METEOSOURCE_API_KEY:
            if _BEDROCK_KB_ID:
                return _suggest_dish_for_time_and_weather(event)
            lines = [_get_time_text(), _get_weather_text(location)]
            lines.append(
                "Recipe suggestions unavailable: BEDROCK_KB_ID is not configured on the Lambda."
            )
            return "\n".join(lines)
        if wants_recipe and not location:
            return (
                f"{_get_time_text()}\n\n"
                "To suggest recipes, please specify a city (e.g. paris, london, tel-aviv)."
            )

    return _get_time_text()


def _handle_get_weather(event: Dict[str, Any]) -> str:
    location = _resolve_location(event)
    if not location:
        raise ValueError(
            "Location parameter is required (or mention a city in the request)."
        )

    text = _input_text(event)
    wants_recipe = _wants_recipe_suggestion(text) or bool(_BEDROCK_KB_ID)

    if wants_recipe and _BEDROCK_KB_ID and _METEOSOURCE_API_KEY:
        return _suggest_dish_for_time_and_weather(event)

    return _get_weather_text(location)


def _share_recipe_with_buddy(event: Dict[str, Any]) -> str:
    buddy_name = (_param_value(event, "buddy_name") or "").strip()
    recipe_title = (_param_value(event, "recipe_title") or "").strip()
    recipe_body = (_param_value(event, "recipe_body") or "").strip()

    if not buddy_name:
        raise ValueError("buddy_name parameter is required")
    if not recipe_title:
        raise ValueError("recipe_title parameter is required")
    if not recipe_body:
        raise ValueError("recipe_body parameter is required")

    session_attrs = event.get("sessionAttributes") or {}
    user_id = (session_attrs.get("user_id") or "").strip()
    sender_name = (session_attrs.get("sender_name") or "A Smart Cookbook user").strip()

    if not user_id:
        raise ValueError("user_id missing from sessionAttributes")

    if not _AGENT_TOOL_SECRET:
        raise ValueError("AGENT_TOOL_SECRET is not configured on the Lambda")

    payload = json.dumps(
        {
            "user_id": user_id,
            "sender_name": sender_name,
            "buddy_name": buddy_name,
            "recipe_title": recipe_title,
            "recipe_body": recipe_body,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        _FLASK_TOOL_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Agent-Tool-Secret": _AGENT_TOOL_SECRET,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if resp.status != 200 or not body.get("ok"):
                raise Exception(body.get("error") or body.get("message") or "Share failed")
            return str(body.get("message") or "Email queued successfully.")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            message = parsed.get("error") or parsed.get("message") or detail
        except json.JSONDecodeError:
            message = detail or str(exc)
        raise Exception(message) from exc


def _action_response(
    action_group: str,
    function: str,
    text: str,
    message_version: str,
) -> Dict[str, Any]:
    return {
        "response": {
            "actionGroup": action_group,
            "function": function,
            "functionResponse": {
                "responseBody": {"TEXT": {"body": str(text)}},
                "httpStatusCode": 200,
            },
        },
        "messageVersion": str(message_version),
    }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for processing Bedrock agent requests.
    """
    action_group = event.get("actionGroup", "")
    function = event.get("function", "")
    message_version = event.get("messageVersion", "1.0")

    try:
        logger.info(
            "Action request function=%s inputText=%r parameters=%s",
            function,
            _input_text(event),
            event.get("parameters"),
        )

        if function in (
            "SuggestDishForTimeAndWeather",
            "GetWeather",
            "GetTime",
        ):
            if function == "GetTime":
                text = _handle_get_time(event)
            elif function == "GetWeather":
                text = _handle_get_weather(event)
            else:
                text = _suggest_dish_for_time_and_weather(event)
        elif function == "ShareRecipeWithBuddy":
            text = _share_recipe_with_buddy(event)
        else:
            text = f"Unknown function: {function}"

        response = _action_response(action_group, function, text, message_version)
        logger.info("Response sent to Bedrock: %s", response)
        return response

    except KeyError as e:
        logger.error("Missing required field: %s", str(e))
        return {
            "statusCode": HTTPStatus.BAD_REQUEST,
            "body": f"Error: {str(e)}",
        }
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        logger.exception(e)
        error_text = f"Tool error: {str(e)}"
        if action_group and function:
            return _action_response(action_group, function, error_text, message_version)
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR,
            "body": f"Internal server error: {str(e)}",
        }
