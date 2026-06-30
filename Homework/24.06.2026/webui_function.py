"""
title: Netflix OMDb Filter
author: Giora
version: 0.1
description: Intercept movie/show questions and fetch OMDb data from local proxy.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import re
import urllib.request
import urllib.parse
import json


def fetch_movie(title: str) -> Optional[dict]:
    """
    Call the local Flask proxy from INSIDE the container.
    Your Flask must run with: app.run(host="0.0.0.0", port=5005)
    """
    try:
        base_url = "http://host.docker.internal:5005/movie"
        url = base_url + "?title=" + urllib.parse.quote(title)
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except Exception as e:
        # if anything fails, just return None and let the LLM answer normally
        print(f"[omdb-filter] error calling movie API: {e}")
        return None


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        max_turns: int = Field(
            default=20, description="Maximum allowable conversation turns for a user."
        )

    class UserValves(BaseModel):
        max_turns: int = Field(
            default=20, description="Maximum allowable conversation turns for a user."
        )

    def __init__(self):
        self.valves = self.Valves()
        self._last_movie = None

    def _extract_title(self, text: str) -> Optional[str]:
        """
        Very simple extractor:
        - 'tell me about Stranger Things'
        - 'look up The Matrix'
        - 'imdb rating for Inception'
        """
        text_low = text.lower()

        # try some patterns
        m = re.search(r"(?:look up|search for|tell me about|about)\s+(.+)", text_low)
        if m:
            title = m.group(1).strip()
            title = title.rstrip(" ?.")
            return title.title()

        m = re.search(r"(?:imdb rating|poster|plot)\s+(?:for|of)\s+(.+)", text_low)
        if m:
            title = m.group(1).strip()
            title = title.rstrip(" ?.")
            return title.title()

        m = re.search(r"(.+?)\s+(?:poster|imdb rating|plot)", text_low)
        if m:
            title = m.group(1).strip()
            title = title.rstrip(" ?.")
            return title.title()

        return None

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """
        Runs BEFORE LLM.
        If user asked about a movie/show, we fetch OMDb data and inject as system message so LLM can just answer.
        """
        messages: List[Dict[str, Any]] = body.get("messages", [])
        if not messages:
            return body

        last_msg = messages[-1]
        content = last_msg.get("content") or last_msg.get("text") or ""

        title = self._extract_title(content)
        if not title:
            # no movie/show request → just return
            return body

        # call our local API
        movie = fetch_movie(title)
        if not movie:
            # if failed, just return original
            return body

        self._last_movie = movie
        poster = movie.get("poster") or "N/A"

        # build a helper message for the model
        # we inject BEFORE the user's message so the model "knows"
        helper_msg = {
            "role": "system",
            "content": (
                f"The user asked about '{title}'.\n"
                f"IMPORTANT: The Netflix knowledge base does NOT contain poster URLs or IMDb ratings.\n"
                f"Use this OMDb API data instead:\n"
                f"- Poster URL: {poster}\n"
                f"- IMDb Rating: {movie.get('imdb_rating', 'N/A')}\n"
                f"- Plot: {movie.get('plot', 'N/A')}\n"
                f"Full OMDb response: {json.dumps(movie)}\n"
                f"You MUST include the poster URL in your answer. If the poster URL is not N/A, share it as a markdown link."
            ),
        }

        # insert helper message right before the last user message
        body["messages"] = messages[:-1] + [helper_msg, last_msg]

        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # append poster link so it always appears even if the LLM ignores injected OMDb data
        movie = self._last_movie
        self._last_movie = None

        if not movie:
            return body

        poster = movie.get("poster")
        if not poster or poster == "N/A":
            return body

        messages: List[Dict[str, Any]] = body.get("messages", [])
        if not messages:
            return body

        last_msg = messages[-1]
        content = last_msg.get("content") or last_msg.get("text") or ""
        if poster in content:
            return body

        title = movie.get("title") or "Poster"
        last_msg["content"] = (
            content
            + f"\n\n**Poster for {title}:** [{poster}]({poster})\n\n"
            + f"![{title} poster]({poster})"
        )

        return body
