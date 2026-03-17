from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import cv2
import face_recognition
import numpy as np
from pathlib import Path
from datetime import timedelta
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# ---------------------- FLASK SETUP ----------------------
app = Flask(__name__)
app.secret_key = "sparkgenx_secret_key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ---------------------- LOGIN CONFIG ----------------------
DEFAULT_USER = {"username": "officer", "password": "1234@567"}

# ---------------------- EMAIL CONFIG ----------------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
ADMIN_EMAILS = [
    "munnareddy1311@gmail.com"
]
# --- ADMIN EMAIL CONFIGURATION ---
SENDER_EMAIL = "munnareddy1311@gmail.com"       # your gmail (must allow app passwords)
SENDER_PASSWORD = "pygw rmyl appk aeso"      # not your real password! (use App Password)


# ---------------------- FACE DETECTION ----------------------
def detect_and_crop_face(image_path):
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise ValueError("❌ Could not read image from path")

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
    )
    if len(faces) == 0:
        raise ValueError("❌ No faces detected — use a clearer image.")

    x, y, w, h = faces[0]
    face_crop = image_bgr[y:y + h, x:x + w]
    face_rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
    face_rgb = np.ascontiguousarray(face_rgb, dtype=np.uint8)

    temp_file = os.path.join(tempfile.gettempdir(), "cropped_face.jpg")
    cv2.imwrite(temp_file, cv2.cvtColor(face_rgb, cv2.COLOR_RGB2BGR))
    return temp_file


# ---------------------- VIDEO SEARCH ----------------------
def search_person_in_video(person_image_path, video_path, tolerance=0.45, frame_skip=5):
    cropped_face_path = detect_and_crop_face(person_image_path)
    person_image = face_recognition.load_image_file(cropped_face_path)
    person_encodings = face_recognition.face_encodings(person_image)
    if not person_encodings:
        raise ValueError("❌ Could not encode the face.")
    person_encoding = person_encodings[0]

    video = cv2.VideoCapture(video_path)
    if not video.isOpened():
        raise ValueError("❌ Could not open video file.")

    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = video.get(cv2.CAP_PROP_FPS)

    frame_number = 0
    found = False
    snapshot_path = None
    timestamp = None

    while True:
        ret, frame = video.read()
        if not ret:
            break
        frame_number += 1
        if frame_number % frame_skip != 0:
            continue

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for face_encoding, (top, right, bottom, left) in zip(face_encodings, face_locations):
            match = face_recognition.compare_faces([person_encoding], face_encoding, tolerance=tolerance)[0]
            if match:
                timestamp = str(timedelta(seconds=int(frame_number / fps)))
                snapshot_path = os.path.join(app.config["UPLOAD_FOLDER"], f"match_{Path(video_path).stem}.jpg")
                cv2.imwrite(snapshot_path, frame)
                found = True
                break

        if found:
            break

    video.release()
    return {
        "found": found,
        "frame": frame_number if found else None,
        "timestamp": timestamp if found else None,
        "snapshot": snapshot_path if found else None,
    }


# ---------------------- EMAIL ALERT ----------------------
def send_alert_email(snapshot_path, timestamp, video_name):
    """Send email alert when a missing person is found."""
    try:
        subject = "🚨 ALERT: Missing Person Found in Surveillance Video"
        body = f"""
        A missing person match has been detected in the uploaded surveillance video.

        📹 Video File: {video_name}
        🕒 Timestamp: {timestamp}

        The matching face snapshot is attached for verification.
        """

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ", ".join(ADMIN_EMAILS)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # attach snapshot if available
        if snapshot_path and os.path.exists(snapshot_path):
            with open(snapshot_path, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype="jpg")
                attachment.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=os.path.basename(snapshot_path)
                )
                msg.attach(attachment)

        # send email
        print("📧 Connecting to Gmail SMTP...")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.set_debuglevel(1)  # show server responses
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print("✅ Alert email sent successfully to:", ", ".join(ADMIN_EMAILS))

    except Exception as e:
        print("❌ Error sending email:", e)


# ---------------------- ROUTES ----------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == DEFAULT_USER["username"] and password == DEFAULT_USER["password"]:
            session["user"] = username
            return redirect(url_for("search"))
        else:
            flash("Invalid credentials. Try again.")
    return render_template("login.html")


@app.route("/search", methods=["POST"])
@app.route("/search", methods=["GET", "POST"])
def search():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        # Render the HTML page so the officer can upload files
        return render_template("search.html")

    # POST logic (when the form submits files)
    image_file = request.files.get("person_image")
    video_file = request.files.get("video_file")

    if not image_file or not video_file:
        return jsonify({"error": "Missing files"}), 400

    img_path = os.path.join(app.config["UPLOAD_FOLDER"], image_file.filename)
    vid_path = os.path.join(app.config["UPLOAD_FOLDER"], video_file.filename)
    image_file.save(img_path)
    video_file.save(vid_path)

    try:
        result = search_person_in_video(img_path, vid_path)
        if result["found"]:
            send_alert_email(result["snapshot"], result["timestamp"], os.path.basename(vid_path))
            return jsonify({
                "found": True,
                "timestamp": result["timestamp"],
                "snapshot": f"/{result['snapshot']}"
            })
        else:
            return jsonify({"found": False})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ---------------------- MAIN ----------------------
if __name__ == "__main__":
    app.run(debug=True)
