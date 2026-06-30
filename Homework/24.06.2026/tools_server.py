import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv(Path(__file__).parent / ".env")

OMDB_API_KEY = os.getenv("OMDB_API_KEY")
OMDB_BASE_URL = "https://www.omdbapi.com/"

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/movie")
def get_movie():
    """Look up a movie or TV show by title using the OMDb API."""
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "Missing required query parameter: title"}), 400

    if not OMDB_API_KEY:
        return jsonify({"error": "OMDB_API_KEY is not configured"}), 500

    try:
        response = requests.get(
            OMDB_BASE_URL,
            params={"t": title, "apikey": OMDB_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"Failed to reach OMDb API: {exc}"}), 502

    data = response.json()

    if data.get("Response") == "False":
        return jsonify({"error": data.get("Error", "Title not found")}), 404

    return jsonify(
        {
            "title": data.get("Title"),
            "year": data.get("Year"),
            "rated": data.get("Rated"),
            "runtime": data.get("Runtime"),
            "genre": data.get("Genre"),
            "director": data.get("Director"),
            "actors": data.get("Actors"),
            "plot": data.get("Plot"),
            "imdb_rating": data.get("imdbRating"),
            "type": data.get("Type"),
            "poster": data.get("Poster"),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
