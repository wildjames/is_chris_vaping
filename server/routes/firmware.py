import hashlib
import zipfile
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import select

from extensions import FIRMWARE_DIR, Session, require_token
from models import Firmware

firmware_bp = Blueprint("firmware", __name__)

FIRMWARE_NAME = "firmware.zip"


@firmware_bp.route("/firmware/latest", methods=["GET"])
def firmware_latest():
    """Returns metadata about the latest firmware version from MariaDB."""
    session = Session()
    try:
        fw = session.execute(
            select(Firmware).order_by(Firmware.id.desc())
        ).scalars().first()
        if not fw:
            return jsonify({"error": "No firmware available"}), 404

        firmware_path = FIRMWARE_DIR / FIRMWARE_NAME
        if firmware_path.is_file():
            file_size = firmware_path.stat().st_size
            hasher = hashlib.sha256()
            with firmware_path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    hasher.update(chunk)
            file_hash = hasher.hexdigest()
        else:
            file_size = fw.size
            file_hash = fw.sha256

        return jsonify({
            "version": fw.version,
            "size": file_size,
            "sha256": file_hash,
            "uploaded_at": fw.uploaded_at.isoformat() if fw.uploaded_at else None,
        }), 200
    finally:
        session.close()


@firmware_bp.route("/firmware/download", methods=["GET"])
def firmware_download():
    """Download the latest firmware DFU package (ZIP)."""
    session = Session()
    try:
        fw = session.execute(
            select(Firmware).order_by(Firmware.id.desc())
        ).scalars().first()
        if not fw:
            return jsonify({"error": "No firmware available"}), 404
        version = fw.version
    finally:
        session.close()

    firmware_path = FIRMWARE_DIR / FIRMWARE_NAME
    if not firmware_path.is_file():
        return jsonify({"error": "Firmware file missing"}), 404
    return send_file(firmware_path, mimetype="application/zip",
                     download_name=f"firmware-{version}.zip")


@firmware_bp.route("/firmware/upload", methods=["POST"])
@require_token
def firmware_upload():
    """Upload a new firmware DFU package (ZIP). Persists metadata to MariaDB."""
    version = request.args.get("version")
    if not version:
        return jsonify({"error": "version query parameter required"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = FIRMWARE_DIR / "firmware.zip.tmp"
    firmware_path = FIRMWARE_DIR / FIRMWARE_NAME
    file.save(temp_path)

    if not zipfile.is_zipfile(temp_path):
        temp_path.unlink()
        return jsonify({"error": "Uploaded file is not a valid ZIP"}), 400
    with zipfile.ZipFile(temp_path, "r") as zf:
        if "manifest.json" not in zf.namelist():
            temp_path.unlink()
            return jsonify({"error": "ZIP missing manifest.json — use adafruit-nrfutil dfu genpkg to create the package"}), 400

    file_size = temp_path.stat().st_size
    hasher = hashlib.sha256()

    with temp_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            hasher.update(chunk)

    file_hash = hasher.hexdigest()
    now = datetime.now(timezone.utc)

    session = Session()
    try:
        session.add(Firmware(version=version, size=file_size, sha256=file_hash, uploaded_at=now))
        session.commit()
    except Exception:
        session.rollback()
        temp_path.unlink(missing_ok=True)
        current_app.logger.exception("Failed to persist firmware metadata to DB")
        return jsonify({"error": "Database write failed"}), 500
    finally:
        session.close()

    temp_path.replace(firmware_path)

    current_app.logger.info("Firmware uploaded: version=%s size=%d sha256=%s", version, file_size, file_hash)
    return jsonify({"status": "ok", "version": version, "size": file_size, "sha256": file_hash}), 200
