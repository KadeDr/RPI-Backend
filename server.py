import json
import os

import requests
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge


APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS", "https://docs.team5103.com"
    ).split(",")
    if origin.strip()
]

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000
CORS(
    app,
    resources={r"/api": {"origins": ALLOWED_ORIGINS}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


def error_response(message, code, status):
    return jsonify({"status": "error", "message": message, "code": code}), status


@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return error_response("Request body is too large.", "PAYLOAD_TOO_LARGE", 413)


@app.route("/api", methods=["GET", "POST"])
def proxy_api():
    if not APPS_SCRIPT_URL.startswith("https://"):
        return error_response(
            "The documentation service is not configured.",
            "UPSTREAM_NOT_CONFIGURED",
            503,
        )

    if request.method == "POST":
        body = request.get_data(cache=False)
        if not body:
            return error_response("No JSON payload was provided.", "EMPTY_BODY", 400)
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")
        except (json.JSONDecodeError, ValueError):
            return error_response(
                "The request body must be valid JSON.", "INVALID_JSON", 400
            )

    try:
        if request.method == "GET":
            upstream = requests.get(
                APPS_SCRIPT_URL,
                params=request.args.items(multi=True),
                timeout=30,
                allow_redirects=True,
            )
        else:
            upstream = requests.post(
                APPS_SCRIPT_URL,
                data=body,
                headers={"Content-Type": "text/plain;charset=utf-8"},
                timeout=30,
                allow_redirects=True,
            )

    except requests.RequestException:
        return error_response(
            "The documentation service is unavailable.",
            "UPSTREAM_UNAVAILABLE",
            503,
        )

    try:
        if len(upstream.content) > 5_000_000:
            raise ValueError("upstream response is too large")
        json.loads(upstream.content)
    except (json.JSONDecodeError, ValueError):
        return error_response(
            "The documentation service is unavailable.",
            "UPSTREAM_UNAVAILABLE",
            503,
        )

    response = Response(
        upstream.content,
        status=upstream.status_code,
        content_type="application/json; charset=utf-8",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz")
def health():
    return jsonify({"status": "ok" if APPS_SCRIPT_URL.startswith("https://") else "degraded"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000)
