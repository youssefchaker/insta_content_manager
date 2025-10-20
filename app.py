# app.py
import json
import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, redirect, url_for, render_template, flash, session
from werkzeug.utils import secure_filename
from flask_apscheduler import APScheduler
import subprocess
from models import init_db, SessionLocal, ScheduledItem, StatusEnum
from uploader import IGPoster
from sqlalchemy import select
from dotenv import load_dotenv
from auth import auth_bp, login_required

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# --- CONFIG ---
UPLOAD_FOLDER = Path("static/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE = {".png", ".jpg", ".jpeg"}
ALLOWED_VIDEO = {".mp4", ".mov", ".mkv", ".avi"}
MAX_DURATION_STORY = 60
MAX_DURATION_POST = 60

init_db()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["SCHEDULER_API_ENABLED"] = True
app.secret_key = os.getenv("FLASK_SECRET")
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# IG poster instance (login done on demand)
app.register_blueprint(auth_bp)

@app.template_filter('to_local_time')
def to_local_time_filter(utc_dt):
    """Converts a naive UTC datetime to a local datetime string."""
    if not utc_dt:
        return ""
    # The stored time is naive but represents UTC. Make it aware.
    aware_utc = utc_dt.replace(tzinfo=timezone.utc)
    # Convert to the system's local timezone and format for display.
    return aware_utc.astimezone().strftime('%Y-%m-%d %H:%M')

@app.template_filter('basename')
def basename_filter(path):
    """Extracts the basename from a path string."""
    if not path:
        return ""
    return os.path.basename(path)

# Helper: run ffprobe to get video duration (seconds)
def get_video_duration(path: Path) -> float:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return float(out.strip())
    except Exception as e:
        logger.exception("ffprobe error: %s", e)
        return 0.0

# Route: index + upload form + queue
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    session_db = SessionLocal()
    if request.method == "POST":
        file = request.files.get("media")
        post_type = request.form.get("post_type")  # 'post' or 'story'
        caption = request.form.get("caption", "")
        scheduled_str = request.form.get("scheduled_time")

        if not file:
            flash("No file uploaded", "danger")
            return redirect(url_for("index"))

        # parse scheduled time (input type=datetime-local returns 'YYYY-MM-DDTHH:MM')
        try:
            # The input is naive (no timezone). We interpret it as the user's local time,
            # attach the system's local timezone, then convert to UTC for storage.
            local_dt = datetime.fromisoformat(scheduled_str)
            utc_dt = local_dt.astimezone(timezone.utc)
            scheduled_time = utc_dt.replace(tzinfo=None)
        except Exception:
            flash("Invalid scheduled time", "danger")
            return redirect(url_for("index"))

        filename_raw = secure_filename(file.filename)
        ext = Path(filename_raw).suffix.lower()

        if ext in ALLOWED_IMAGE:
            media_type = "image"
        elif ext in ALLOWED_VIDEO:
            media_type = "video"
        else:
            flash("Unsupported file type", "danger")
            return redirect(url_for("index"))

        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_path = UPLOAD_FOLDER / unique_name
        file.save(save_path)

        if media_type == "video":
            duration = get_video_duration(save_path)
            limit = MAX_DURATION_STORY if post_type == "story" else MAX_DURATION_POST
            if duration <= 0:
                flash("Could not read video duration; make sure ffprobe is installed", "danger")
                save_path.unlink(missing_ok=True)
                return redirect(url_for("index"))
            if duration > limit:
                save_path.unlink(missing_ok=True)
                flash(f"Video too long for {post_type}. Duration {duration:.1f}s > limit {limit}s", "danger")
                return redirect(url_for("index"))

        # Insert into DB
        item = ScheduledItem(
            filename=str(save_path),
            media_type=media_type,
            post_type=post_type,
            scheduled_time=scheduled_time,
            status=StatusEnum.scheduled,
            caption=caption
        )
        session_db.add(item)
        session_db.commit()

        flash("Scheduled successfully", "success")
        logger.info("Scheduled new item id=%s file=%s at %s", item.id, item.filename, scheduled_time)
        return redirect(url_for("index"))

    items = session_db.execute(select(ScheduledItem).order_by(ScheduledItem.scheduled_time)).scalars().all()
    return render_template("index.html", items=items, now=datetime.utcnow())

# Route: returns just the queue table HTML for polling
@app.route("/queue-partial")
@login_required
def queue_partial():
    session_db = SessionLocal()
    items = session_db.execute(select(ScheduledItem).order_by(ScheduledItem.scheduled_time)).scalars().all()
    session_db.close()
    return render_template("_queue.html", items=items)


# Route: delete a single item
@app.route("/delete/<int:item_id>", methods=["POST"])
@login_required
def delete_item(item_id):
    session_db = SessionLocal()
    item = session_db.get(ScheduledItem, item_id)
    if item:
        try:
            file_path = Path(item.filename)
            file_path.unlink(missing_ok=True)

            session_db.delete(item)
            session_db.commit()
            flash(f"Deleted item {item_id} successfully.", "success")
            logger.info("Deleted item id=%s file=%s", item.id, item.filename)
        except Exception as e:
            session_db.rollback()
            logger.exception("Error deleting item %s: %s", item_id, e)
            flash(f"Error deleting item {item_id}.", "danger")
    else:
        flash(f"Item {item_id} not found.", "warning")
    return redirect(url_for("index"))

def clear_all_data():
    session_db = SessionLocal()
    try:
        for f in UPLOAD_FOLDER.glob("*"):
            if f.is_file():
                f.unlink()
        session_db.query(ScheduledItem).delete()
        session_db.commit()
        logger.info("Cleared all scheduled items and media files.")
    except Exception as e:
        logger.exception("An error occurred while clearing data: %s", e)
        session_db.rollback()
    finally:
        session_db.close()

app.clear_all_data = clear_all_data

# Route: clear all data (DB and files)
@app.route("/clear-all", methods=["POST"])
@login_required
def clear_all():
    app.clear_all_data()
    session.clear()
    flash("Cleared all scheduled items and media files.", "success")
    return redirect(url_for("index"))

import json

# Background job: runs every 30 seconds to check for due items
@scheduler.task("interval", id="uploader_task", seconds=10, misfire_grace_time=30)
def check_and_upload():
    with app.app_context():
        credentials = {}
        try:
            with open("credentials.json", "r") as f:
                credentials = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("No valid credentials file found. Skipping upload check.")
            return

        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            logger.info("Username or password not in credentials file. Skipping upload check.")
            return

        # Find and lock one due item to prevent double-uploads
        with SessionLocal() as session_db:
            now = datetime.utcnow()
            item_to_process = session_db.execute(
                select(ScheduledItem).where(ScheduledItem.scheduled_time <= now, ScheduledItem.status == StatusEnum.scheduled).limit(1)
            ).scalar_one_or_none()

            if not item_to_process:
                return

            # Lock the item by changing its status
            item_to_process.status = StatusEnum.processing
            session_db.commit()
            item_id = item_to_process.id
            filename = item_to_process.filename
            post_type = item_to_process.post_type
            caption = item_to_process.caption

        logger.info("Processing item id=%s file=%s", item_id, filename)
        with SessionLocal() as session_db:
            try:
                ig = IGPoster(username, password)
                item = session_db.get(ScheduledItem, item_id)
                success, msg = ig.upload(filename, post_type, caption=caption)
                if success:
                    item.status = StatusEnum.uploaded
                    item.log = (item.log or "") + f"\n{datetime.utcnow().isoformat()} Uploaded: {msg}"
                else:
                    item.status = StatusEnum.failed
                    item.log = (item.log or "") + f"\n{datetime.utcnow().isoformat()} Failed: {msg}"
            except Exception as e:
                item = session_db.get(ScheduledItem, item_id) # Re-fetch in case of session error
                item.status = StatusEnum.failed
                item.log = (item.log or "") + f"\n{datetime.utcnow().isoformat()} Exception: {e}"
            session_db.commit()
            logger.info("Finished processing item id=%s with status %s", item_id, item.status.value)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
