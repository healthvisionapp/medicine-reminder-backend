import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, abort
import firebase_admin
from firebase_admin import credentials, firestore, auth as fb_auth
import pytz
import json

app = Flask(__name__)

# --- Initialize Firebase ---
firebase_secret = os.getenv("FIREBASE_SERVICE_ACCOUNT")

if firebase_secret:
    cred = credentials.Certificate(json.loads(firebase_secret))
else:
    cred = credentials.Certificate("serviceAccountKey.json")

firebase_admin.initialize_app(cred)
db = firestore.client()
print("✅ Firebase initialized successfully!")

# --- Pakistan timezone ---
PK_TZ = pytz.timezone("Asia/Karachi")

# --- Helper: Convert time string to next datetime ---
def get_next_datetime_from_time_str(time_str: str):
    now = datetime.now(PK_TZ)
    target = datetime.strptime(time_str, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day, tzinfo=PK_TZ
    )
    if target < now:
        target += timedelta(days=1)
    return target

# --- Frontend form ---
@app.route("/", methods=["GET"])
def index():
    return render_template("reminder_form.html", success=False)

@app.route("/set_reminder", methods=["POST"])
def set_reminder():
    id_token = request.form.get("idToken")
    if not id_token:
        abort(401, "Missing idToken")

    try:
        decoded = fb_auth.verify_id_token(id_token)
        uid = decoded["uid"]
        print("✅ Token verified for UID:", uid)
    except Exception as e:
        print("❌ Invalid token:", e)
        abort(401, "Invalid idToken")

    medicine = request.form.get("medicine")
    dosage = request.form.get("dosage")
    time_str = request.form.get("time")
    daily = True if request.form.get("daily") == "on" else False

    next_time = get_next_datetime_from_time_str(time_str)

    reminder_data = {
        "medicine": medicine,
        "dosage": dosage,
        "time_of_day": time_str,
        "daily": daily,
        "next_time": next_time.isoformat(),
        "timestamp_set": datetime.now(PK_TZ).isoformat(),
        "sent": False
    }

    db.collection("users").document(uid).collection("medicines").add(reminder_data)
    print(f"✅ Reminder saved for {medicine} at {time_str}")

    return render_template("reminder_form.html", success=True)

# --- Polling endpoint (React Native frontend) ---
@app.route("/alarm_status", methods=["GET"])
def alarm_status():
    now = datetime.now(PK_TZ)
    current_time = now.strftime("%H:%M")

    try:
        user_docs = db.collection("users").get()
        for user_doc in user_docs:
            meds_ref = db.collection("users").document(user_doc.id).collection("medicines").get()
            for doc in meds_ref:
                med = doc.to_dict()
                if med.get("time_of_day") == current_time:
                    print(f"⏰ Time match for {med.get('medicine')}")
                    return jsonify({"alarm": True, "message": f"{med['medicine']} ({med['dosage']})"})
    except Exception as e:
        print("❌ Error in alarm_status:", e)

    return jsonify({"alarm": False})

# --- Health check ---
@app.route("/health")
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
