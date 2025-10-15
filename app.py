# app.py
import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename
from flask_apscheduler import APScheduler
import subprocess
from models import init_db, SessionLocal, ScheduledItem, StatusEnum
from uploader import IGPoster
from sqlalchemy import select
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# --- CONFIG ---
UPLOAD_FOLDER = Path("static/uploads")
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE = {".png", ".jpg", ".jpeg"}
ALLOWED_VIDEO = {".mp4", ".mov", ".mkv", ".avi"}
MAX_DURATION_STORY = 60  # seconds
MAX_DURATION_POST = 60   # seconds
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# Initialize DB
init_db()

# Flask + scheduler
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["SCHEDULER_API_ENABLED"] = True
app.secret_key = os.getenv("FLASK_SECRET")
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# IG poster instance (login done on demand)
ig = IGPoster(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)

# --- Template Filters ---
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
def index():
    session = SessionLocal()
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
            scheduled_time = utc_dt.replace(tzinfo=None) # Store as naive UTC
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

        # Save file with unique name
        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_path = UPLOAD_FOLDER / unique_name
        file.save(save_path)

        # If video, check duration limits
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
        session.add(item)
        session.commit()

        flash("Scheduled successfully", "success")
        logger.info("Scheduled new item id=%s file=%s at %s", item.id, item.filename, scheduled_time)
        return redirect(url_for("index"))

    # GET: show queue
    items = session.execute(select(ScheduledItem).order_by(ScheduledItem.scheduled_time)).scalars().all()
    return render_template("index.html", items=items, now=datetime.utcnow())

# Route: returns just the queue table HTML for polling
@app.route("/queue-partial")
def queue_partial():
    session = SessionLocal()
    items = session.execute(select(ScheduledItem).order_by(ScheduledItem.scheduled_time)).scalars().all()
    session.close()
    return render_template("_queue.html", items=items)


# Route: delete a single item
@app.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    session = SessionLocal()
    item = session.get(ScheduledItem, item_id)
    if item:
        try:
            # Delete file from disk
            file_path = Path(item.filename)
            file_path.unlink(missing_ok=True)

            # Delete record from DB
            session.delete(item)
            session.commit()
            flash(f"Deleted item {item_id} successfully.", "success")
            logger.info("Deleted item id=%s file=%s", item.id, item.filename)
        except Exception as e:
            session.rollback()
            logger.exception("Error deleting item %s: %s", item_id, e)
            flash(f"Error deleting item {item_id}.", "danger")
    else:
        flash(f"Item {item_id} not found.", "warning")
    return redirect(url_for("index"))

# Route: clear all data (DB and files)
@app.route("/clear-all", methods=["POST"])
def clear_all():
    session = SessionLocal()
    try:
        # Delete all files in upload folder
        for f in UPLOAD_FOLDER.glob("*"):
            if f.is_file():
                f.unlink()
        # Delete all records from DB
        session.query(ScheduledItem).delete()
        session.commit()
        flash("Cleared all scheduled items and media files.", "success")
    except Exception as e:
        flash(f"An error occurred while clearing data: {e}", "danger")
    return redirect(url_for("index"))

# Background job: runs every 30 seconds to check for due items
@scheduler.task("interval", id="uploader_task", seconds=10, misfire_grace_time=30)
def check_and_upload():
    with app.app_context():
        # Find and lock one due item to prevent double-uploads
        with SessionLocal() as session:
            now = datetime.utcnow()
            item_to_process = session.execute(
                select(ScheduledItem).where(ScheduledItem.scheduled_time <= now, ScheduledItem.status == StatusEnum.scheduled).limit(1)
            ).scalar_one_or_none()

            if not item_to_process:
                return # No items are due

            # Lock the item by changing its status
            item_to_process.status = StatusEnum.processing
            session.commit()
            item_id = item_to_process.id
            filename = item_to_process.filename
            post_type = item_to_process.post_type
            caption = item_to_process.caption

        # Now, perform the upload outside the initial lock-grabbing session
        logger.info("Processing item id=%s file=%s", item_id, filename)
        with SessionLocal() as session:
            try:
                item = session.get(ScheduledItem, item_id)
                success, msg = ig.upload(filename, post_type, caption=caption)
                if success:
                    item.status = StatusEnum.uploaded
                    item.log = (item.log or "") + f"\n{datetime.utcnow().isoformat()} Uploaded: {msg}"
                else:
                    item.status = StatusEnum.failed
                    item.log = (item.log or "") + f"\n{datetime.utcnow().isoformat()} Failed: {msg}"
            except Exception as e:
                item = session.get(ScheduledItem, item_id) # Re-fetch in case of session error
                item.status = StatusEnum.failed
                item.log = (item.log or "") + f"\n{datetime.utcnow().isoformat()} Exception: {e}"
            session.commit()
            logger.info("Finished processing item id=%s with status %s", item_id, item.status.value)

if __name__ == "__main__":
    # Run Flask dev server (use production server for real deployments)
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
