"""
Flask API for the extension.

Structure:
1. App setup and CORS so the browser extension can call this API.
2. Helper utilities for validating input and summarizing optional content analysis.
3. `/analyze` for phishing-header analysis, with optional body/content payload support.
4. `/ping` for a simple health check.
"""

from typing import Any

from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # needed so the extension can call this from the browser


def json_error(message: str, status_code: int = 400):
    """Return a consistent JSON error response."""
    return jsonify({"error": message}), status_code


def summarize_content_analysis(content: dict) -> dict:
    """Create a compact summary of the extension's body/content analysis."""
    high_risk = content.get("highRiskFactors", []) or []
    warnings = content.get("warnings", []) or []
    links = content.get("links", []) or []
    body_text = content.get("body", "") or ""

    return {
        "body_length": content.get("bodyLength", len(body_text)),
        "link_count": content.get("linkCount", len(links)),
        "high_risk_count": len(high_risk),
        "warning_count": len(warnings),
        "flags": [
            *(str(item.get("detail") or item.get("text") or item.get("type")) for item in high_risk if isinstance(item, dict)),
            *(str(item.get("detail") or item.get("text") or item.get("type")) for item in warnings if isinstance(item, dict)),
        ],
    }


@app.route("/analyze", methods=["POST"])
def analyze():
    """Analyze Gmail headers and optionally attach content/body analysis."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return json_error("Invalid or missing JSON body.")

    headers = body.get("headers")
    if not isinstance(headers, dict):
        return json_error("'headers' must be provided as an object.")

    context = body.get("context", {})
    if context is not None and not isinstance(context, dict):
        return json_error("'context' must be an object when provided.")

    content_analysis = body.get("content_analysis") or body.get("content")
    if content_analysis is not None and not isinstance(content_analysis, dict):
        return json_error("'content_analysis' (or 'content') must be an object when provided.")

    # If `header_analysis.py` is not ready yet, we fall back to raw echo mode
    # so you can still test the extraction part works.
    try:
        from header_analysis import analyze_headers
        result: dict[str, Any] = analyze_headers(headers)
    except Exception as e:
        # Fallback: just echo the raw headers back so you can verify extraction.
        result = {
            "warning": f"header_analyzer not loaded: {str(e)}",
            "raw_headers_received": headers
        }

    # Preserve the original header-analysis response shape, and add context/content
    # as extra top-level fields for the popup UI.
    result["request_context"] = context

    if content_analysis is not None:
        result["content_analysis"] = content_analysis
        result["content_summary"] = summarize_content_analysis(content_analysis)
    else:
        result["content_analysis"] = None

    return jsonify(result)


@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint to confirm the Flask server is running."""
    return jsonify({"status": "ok", "message": "API is running"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)