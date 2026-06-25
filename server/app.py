import json
import logging
import os
from datetime import datetime, timezone
from functools import wraps

import qrcode
from flask import Flask, jsonify, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

AUTH_TOKEN = os.environ.get("VAPE_API_TOKEN")
if not AUTH_TOKEN:
    raise RuntimeError("VAPE_API_TOKEN environment variable must be set")
SERVER_URL = os.environ.get("VAPE_SERVER_URL", "http://localhost:5000/")

payload = json.dumps({"server_url": SERVER_URL, "auth_token": AUTH_TOKEN})
img = qrcode.make(payload)
qr_code_filename = "/output/vape_config_qr.png"
os.makedirs(os.path.dirname(qr_code_filename), exist_ok=True)
img.save(qr_code_filename)

logger = logging.getLogger(__name__)
logger.info(f"QR code saved to {qr_code_filename}")

# In-memory state
vape_state = {
    "coil_a": False,
    "coil_b": False,
    "last_event": None,
    "last_updated": None,
}


def require_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != AUTH_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/vape-update", methods=["POST"])
@require_token
def vape_update():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    coil = data.get("coil")
    event = data.get("event")

    if coil not in ("coil_a", "coil_b"):
        return jsonify({"error": "Invalid coil, must be coil_a or coil_b"}), 400
    if event not in ("started", "stopped"):
        return jsonify({"error": "Invalid event, must be started or stopped"}), 400

    vape_state[coil] = event == "started"
    vape_state["last_event"] = f"{coil}:{event}"
    vape_state["last_updated"] = datetime.now(timezone.utc).isoformat()

    is_vaping = vape_state["coil_a"] or vape_state["coil_b"]
    app.logger.info(
        "Vape update: %s %s | vaping=%s", coil, event, is_vaping
    )

    return jsonify({"status": "ok", "is_vaping": is_vaping, "state": vape_state}), 200


@app.route("/vape-status", methods=["GET"])
def vape_status():
    is_vaping = vape_state["coil_a"] or vape_state["coil_b"]
    return jsonify({"is_vaping": is_vaping, "state": vape_state}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
