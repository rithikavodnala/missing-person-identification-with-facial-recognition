from flask import Flask, render_template, request, redirect, url_for
import os, csv, smtplib
from werkzeug.utils import secure_filename
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
CSV_FILE = 'reports.csv'

# --- ADMIN EMAIL CONFIGURATION ---
ADMIN_EMAIL = "vodnalarithika@gmail.com"        # where the notification goes
SENDER_EMAIL = "rithikavodnala@gmail.com"       # your gmail (must allow app passwords)
SENDER_PASSWORD = "pygw rmyl appk aeso"      # not your real password! (use App Password)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    fullName = request.form['fullName']
    age = request.form['age']
    gender = request.form['gender']
    lastSeenDate = request.form['lastSeenDate']
    location = request.form['location']
    description = request.form['description']
    contact = request.form['contact']
    additionalInfo = request.form['additionalInfo']
    photo = request.files['photo']

    # Save photo locally
    if photo:
        filename = secure_filename(f"{fullName.replace(' ', '_')}.jpg")
        photo_path = os.path.join(UPLOAD_FOLDER, filename)
        photo.save(photo_path)
    else:
        photo_path = ""

    # Save report to CSV
    file_exists = os.path.isfile(CSV_FILE)
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                'Full Name', 'Age', 'Gender', 'Last Seen Date',
                'Location', 'Description', 'Contact',
                'Additional Info', 'Photo Path', 'Submitted On'
            ])
        writer.writerow([
            fullName, age, gender, lastSeenDate, location,
            description, contact, additionalInfo,
            photo_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])

    # --- SEND EMAIL TO ADMIN ---
    try:
        subject = "🚨 New Missing Person Complaint Filed"
        body = f"""
        A new missing person complaint has been submitted.

        👤 Name: {fullName}
        📅 Last Seen: {lastSeenDate}
        📍 Location: {location}
        📞 Contact: {contact}
        📝 Description: {description}

        Additional Info:
        {additionalInfo}

        Photo saved at: {photo_path}
        """

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()

        print("✅ Email sent to admin successfully!")
    except Exception as e:
        print("❌ Error sending email:", e)

    # Redirect to success page
    return redirect(url_for('success'))

@app.route('/success')
def success():
    return render_template('success.html')

if __name__ == '__main__':
    app.run(debug=True)
