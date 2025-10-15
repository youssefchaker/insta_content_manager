# uploader.py
import os
import logging
from pathlib import Path
from instagrapi import Client

logger = logging.getLogger("uploader")

class IGPoster:
    def __init__(self, username, password, session_file="ig_session.json"):
        self.username = username
        self.password = password
        self.client = None
        self.session_file = session_file
        self.mock = (self.username is None or self.password is None)

    def login(self):
        if self.mock:
            logger.info("IGPoster in MOCK mode (no credentials). Skipping login.")
            return True
        if self.client:
            return True
        self.client = Client()
        try:
            logger.info("Logging in to Instagram as %s", self.username)
            self.client.login(self.username, self.password)
            # save session to avoid re-login (optional)
            try:
                self.client.dump_settings(self.session_file)
            except Exception:
                pass
            logger.info("Instagram login successful")
            return True
        except Exception as e:
            logger.exception("Instagram login failed: %s", e)
            self.client = None
            return False

    def upload(self, file_path: str, post_type: str, caption: str = "") -> (bool, str):
        """
        Uploads file_path as 'post' or 'reel'.
        Returns (success:bool, message:str)
        """
        if self.mock:
            msg = f"[MOCK] Would upload {file_path} as {post_type} with caption: {caption}"
            logger.info(msg)
            return True, msg

        if not self.login():
            return False, "Login failed"

        try:
            if post_type == "post":
                if file_path.lower().endswith(('.jpg','.jpeg','.png')):
                    media = self.client.photo_upload(file_path, caption=caption)
                else:
                    media = self.client.video_upload(file_path, caption=caption)
                return True, f"Uploaded as post: {media.pk}"
            elif post_type == "story":
                if file_path.lower().endswith(('.jpg','.jpeg','.png')):
                    # Captions are not supported directly for story uploads via API
                    media = self.client.photo_upload_to_story(file_path)
                else:
                    media = self.client.video_upload_to_story(file_path)
                return True, f"Uploaded as story: {media.pk}"
            else:
                return False, "Unknown post_type"
        except Exception as e:
            logger.exception("Upload failed: %s", e)
            return False, str(e)