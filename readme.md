# Instagram Content Manager

This is a Flask-based web application that allows you to schedule and automate the posting of content to your Instagram account. You can upload images and videos, write captions, and schedule them to be posted as a feed post or a story at a specific time.

## Features

- **User Authentication:** Securely log in with your Instagram credentials.
- **Media Upload:** Upload images (PNG, JPG, JPEG) and videos (MP4, MOV, MKV, AVI).
- **Post Scheduling:** Schedule your media to be published as a "post" or a "story".
- **Custom Publishing Time:** Choose the exact date and time for your content to go live.
- **Captions:** Add captions to your posts.
- **Content Queue & History:** View the status of all your scheduled, processing, uploaded, and failed posts in a clean and organized queue.
- **Automated Uploading:** A reliable background scheduler checks for due posts every 10 seconds and uploads them automatically.
- **Status Tracking:** Each item in the queue is clearly marked with its current status (Scheduled, Processing, Uploaded, Failed).
- **Content Management:** Delete scheduled items and their associated media files with a single click.
- **Clear All:** A feature to clear all scheduled items and media files.
- **Secure Logout:** Logging out clears all your session data and credentials from the server.

## Technical Specifications

- **Backend:** Python with Flask web framework.
- **Frontend:** HTML, Bootstrap 5, and JavaScript for a responsive and user-friendly interface.
- **Database:** SQLAlchemy with a SQLite database by default. The database URL can be configured using the `DATABASE_URL` environment variable.
- **Scheduling:** Flask-APScheduler for managing and running background jobs.
- **Instagram Integration:** The `instagrapi` library is used for all interactions with the Instagram API.
- **Video Processing:** `ffprobe` is used to get video duration to enforce Instagram's limits.

## Project Structure

```
.
├── .gitignore
├── app.py              # Main Flask application
├── auth.py             # User authentication (login, logout)
├── forms.py            # Login form definition
├── models.py           # SQLAlchemy database schema
├── readme.md           # This file
├── requirements.txt    # Python dependencies
├── uploader.py         # Instagram API interaction
├── static/
│   └── uploads/        # Uploaded media files
└── templates/
    ├── _queue.html     # Partial template for the queue
    ├── index.html      # Main page with upload form and queue
    ├── layout.html     # Base layout for all pages
    └── login.html      # Login page
```

## Getting Started

### Prerequisites

- Python 3.x
- `ffprobe` (part of the FFmpeg project) installed and available in your system's PATH.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/insta_content_manager.git
   cd insta_content_manager
   ```

2. **Create a virtual environment and activate it:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a `.env` file** in the root directory and add the following environment variables:
   ```
   FLASK_SECRET=your_super_secret_key
   DATABASE_URL=sqlite:///./database.db
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Open your browser** and navigate to `http://127.0.0.1:5000`.

## How to Use

1. **Login:** You will be redirected to the login page. Enter your Instagram username and password.
2. **Schedule Content:**
   - Select a media file to upload.
   - Choose whether to post it as a "Post" or a "Story".
   - Select the desired publishing time.
   - Add a caption if you are creating a "Post".
   - Click "Schedule".
3. **Manage Queue:** Your scheduled post will appear in the queue on the right. You can see its status and delete it if needed.
4. **Logout:** When you are done, click "Logout" to securely end your session.

## Disclaimer

This application uses a third-party library to interact with the Instagram API. Use it at your own risk. The developers of this application are not responsible for any actions taken on your Instagram account.
