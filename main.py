import datetime
import json
import requests
import firebase_admin
from firebase_admin import firestore
import functions_framework
from google import genai
from google.genai import types

# --- CONFIGURATION ---
GEMINI_API_KEY = "AIzaSyBcDMlrAkg48nnL8Wy8fHlNm18jjm5yR3c"
WA_TOKEN = "EAAMTn8rGplIBQRiwj4mH9Ck7KlpIVkIRYxxpElLUDtvqLRdcbZBHvyaRIBxDi9RZAtYXGgZAZBAYiTR5oNPENCcB9YVZBZAdocseTHxNwoymB08UM4Ml6c1uRZCpuBQZC5iWL6liod7wdZCEkFCHVkSWDn06rqHS2PXXGQsShgSOGLkcAN6JiaHvkqmPSddE3AxOXSYl5Uktt7unhP6u91vqZCs74hxXQPLXXGZAN1DTNJy"
PHONE_NUMBER_ID = "875111485694772"
VERIFY_TOKEN = "MYSUPERSECRET"

# --- INIT ---
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- HELPERS ---
def _clean_id(user_id):
    if not user_id: return ""
    return "".join(filter(str.isdigit, str(user_id)))

def _first_word(s):
    if not s: return ""
    parts = str(s).strip().split()
    if not parts: return ""
    word = parts[0]
    # If it's just digits, add 'i' prefix for Intervals.icu athlete ID
    if word.isdigit():
        return f"i{word}"
    return word

def send_wa(to, body):
    to_clean = _clean_id(to)
    print(f"SENDING WA to {to_clean}: {body[:50]}...")
    try:
        res = requests.post(
            f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages",
            json={"messaging_product": "whatsapp", "to": to_clean, "type": "text", "text": {"body": body}},
            headers={"Authorization": f"Bearer {WA_TOKEN}"}, timeout=10
        )
        print(f"WA STATUS: {res.status_code}, RESPONSE: {res.text}")
    except Exception as e:
        print(f"Error sending WA: {e}")

def get_user_doc(user_id):
    return db.collection("users").document(_clean_id(user_id)).get().to_dict() or {}

def set_user_credentials(user_id, api_key, athlete_id, name=None):
    # ניקוי יסודי - לוקחים רק את המילה הראשונה ומנקים תווים לא רצויים
    clean_key = _first_word(api_key)
    clean_id = _first_word(athlete_id)
    doc_id = _clean_id(user_id)
    
    data = {
        "intervals_api_key": clean_key,
        "intervals_athlete_id": clean_id,
        "connected_at": firestore.SERVER_TIMESTAMP
    }
    if name:
        data["name"] = name.strip()
    
    print(f"SAVING CREDENTIALS: user_id={user_id} -> doc_id={doc_id}, athlete_id={clean_id}, name={name}")
    
    db.collection("users").document(doc_id).set(data, merge=True)

# --- INTERVALS.ICU LOGIC ---
def fetch_intervals_data(user_id):
    user_doc = get_user_doc(user_id)
    
    api_key = _first_word(user_doc.get("intervals_api_key"))
    athlete_id = _first_word(user_doc.get("intervals_athlete_id"))

    if not api_key or not athlete_id:
        raise Exception("User not connected")

    auth = ('API_KEY', api_key)
    
    today = datetime.date.today()
    oldest = (today - datetime.timedelta(days=14)).isoformat()
    newest = today.isoformat()
    
    wellness_data = []
    try:
        url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/wellness"
        print(f"DEBUG: Fetching wellness from {url} with auth API_KEY:{api_key[:4]} for last 14 days...")
        res = requests.get(url, auth=auth, params={"oldest": oldest, "newest": newest}, timeout=15)
        print(f"DEBUG: Wellness status: {res.status_code}")
        if res.status_code == 200:
            wellness_data = res.json()
            print(f"DEBUG: Received {len(wellness_data)} wellness entries")
        else:
            print(f"DEBUG: Wellness error response: {res.text}")
    except Exception as e:
        print(f"DEBUG: Wellness exception: {e}")

    # נמצא את הרשומה הכי עדכנית שיש בה HRV או דופק מנוחה
    wellness = {}
    doc_id = _clean_id(user_id)
    if wellness_data and isinstance(wellness_data, list):
        batch = db.batch()
        for entry in wellness_data:
            entry_id = entry.get("id")
            if entry_id:
                # Store in history subcollection
                hist_ref = db.collection("users").document(doc_id).collection("wellness_history").document(str(entry_id))
                batch.set(hist_ref, entry, merge=True)
            
            # Check for latest valid record
            hrv = entry.get("hrv") or entry.get("hrv_sdnn")
            rhr = entry.get("restingHR") or entry.get("resting_hr")
            if hrv or rhr:
                wellness = entry
        batch.commit()
        print(f"DEBUG: Saved {len(wellness_data)} entries to history for {doc_id}")
    
    # Fetch some history for trend analysis
    history_docs = db.collection("users").document(doc_id).collection("wellness_history")\
        .order_by("id", direction=firestore.Query.DESCENDING).limit(10).get()
    history_list = [d.to_dict() for d in history_docs]

    # Get Last Activity
    last_activity = None
    try:
        url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/activities"
        print(f"DEBUG: Fetching activities from {url}...")
        res = requests.get(url, auth=auth, params={'limit': 1}, timeout=15)
        print(f"DEBUG: Activities status: {res.status_code}")
        if res.status_code == 200:
            acts = res.json()
            if acts and isinstance(acts, list): 
                last_activity = acts[0]
                print(f"DEBUG: Found last activity: {last_activity.get('name')}")
    except Exception as e:
        print(f"DEBUG: Activities exception: {e}")

    return {
        "user_name": user_doc.get("name", "חבר"),
        "hrv": wellness.get("hrv", "N/A"),
        "resting_hr": wellness.get("restingHR", "N/A"),
        "stress": wellness.get("stressScore", "N/A"),
        "sleep": round(wellness.get("sleepSecs", 0) / 3600, 1) if wellness.get("sleepSecs") else "N/A",
        "last_activity": last_activity,
        "date_found": wellness.get("id", "No recent data found"),
        "history": history_list
    }

# --- AI LOGIC ---
def get_ai_reply(text, data):
    # הכנת מידע על הפעילות האחרונה
    last_act = data.get('last_activity')
    act_info = "No recent activities found"
    if last_act:
        act_info = f"{last_act.get('name')} ({last_act.get('type')}) on {last_act.get('start_date_local')}. Duration: {round(last_act.get('moving_time',0)/60)} min, Distance: {round(last_act.get('distance',0)/1000, 1)} km"

    # הכנת היסטוריה למודל
    history_str = ""
    for h in data.get('history', []):
        history_str += f"- Date {h.get('id')}: HRV {h.get('hrv', 'N/A')}, RHR {h.get('restingHR', 'N/A')}, Sleep {round(h.get('sleepSecs',0)/3600,1) if h.get('sleepSecs') else 'N/A'}h\n"

    prompt = f"""
    You are a trauma-informed emotional regulation coach and physiology expert.
    
    User Profile:
    - Name: {data.get('user_name')}
    
    Current User Physiology (from Intervals.icu):
    - HRV: {data.get('hrv')} ms
    - Resting Heart Rate: {data.get('resting_hr')} bpm
    - Sleep: {data.get('sleep')} hours
    - Stress Score: {data.get('stress')}
    - Latest Data Date: {data.get('date_found')}
    
    Recent History (Last 10 days):
    {history_str}
    
    Last Activity:
    - {act_info}
    
    User Message: "{text}"
    
    Task: 
    1. Always address the user by their name: {data.get('user_name')}.
    2. If the user asks for their metrics, provide current numbers AND mention any interesting trends from the history (e.g., "I see your HRV has been dropping over the last 3 days").
    3. If a value is "N/A", explain that you don't have that specific metric yet.
    4. If they are stressed or have low HRV, offer empathy and a regulation tool.
    5. Respond in Hebrew. Short, empathetic, JSON: {{ "reply": "YOUR_MESSAGE_HERE" }}
    """
    try:
        res = ai_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(res.text).get("reply", "אני כאן איתך.")
    except:
        return "אני מעבד את הנתונים, מיד אענה."

# --- MAIN HANDLER ---
@functions_framework.http
def whatsapp_bot(request):
    print("=== FUNCTION STARTED ===")
    
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200

        if "connect" in request.path and request.args.get("state"):
             state = request.args.get("state")
             return f"""
             <html>
             <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: -apple-system, system-ui, sans-serif; text-align: center; direction: rtl; background: #f0f2f5; padding: 20px; }}
                    .card {{ background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }}
                    h2 {{ color: #1a73e8; }}
                    input {{ width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; font-size: 16px; }}
                    button {{ width: 100%; padding: 15px; background: #28a745; color: white; border: none; border-radius: 8px; font-size: 18px; cursor: pointer; margin-top: 10px; }}
                    .help {{ font-size: 14px; color: #666; text-align: right; margin-top: 20px; background: #fff3cd; padding: 10px; border-radius: 8px; }}
                </style>
             </head>
             <body>
                <div class="card">
                    <h2>חיבור ל-Intervals.icu</h2>
                    <p>הכנס את הפרטים כדי שאוכל לעקוב אחר המדדים שלך:</p>
                    <form method="POST">
                        <input type="hidden" name="phone" value="{state}">
                        <input name="user_name" placeholder="השם שלך" required>
                        <input name="athlete_id" placeholder="Athlete ID (למשל i12345)" required>
                        <input name="api_key" placeholder="API Key (מפתח ארוך)" required>
                        <button type="submit">שמור וסיים</button>
                    </form>
                    <div class="help">
                        <b>איפה מוצאים את זה?</b><br>
                        1. היכנס ל-Intervals.icu<br>
                        2. לך ל-Settings (הגדרות)<br>
                        3. גלול למטה עד לפסקה "API"<br>
                        4. שם תמצא את ה-ID ואת ה-Key.
                    </div>
                </div>
             </body>
             </html>
             """, 200
        return "Access Forbidden", 403

    try:
        # Check for connection form POST first
        if "connect" in request.path and request.method == "POST":
            athlete_id = request.form.get("athlete_id")
            api_key = request.form.get("api_key")
            phone = request.form.get("phone") or request.args.get("state")
            user_name = request.form.get("user_name")
            
            print(f"CONNECT POST: phone={phone}, athlete_id={athlete_id}, name={user_name}")
            
            if phone and api_key and athlete_id:
                set_user_credentials(phone, api_key, athlete_id, user_name)
                welcome_msg = f"✅ היי {user_name or ''}, החיבור הצליח! אני מתחיל לעקוב אחר המדדים שלך. איך אתה מרגיש היום?"
                send_wa(phone, welcome_msg.strip())
                return """
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body { font-family: -apple-system, system-ui, sans-serif; text-align: center; direction: rtl; background: #f0f2f5; padding: 50px 20px; }
                        .card { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }
                        h2 { color: #28a745; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>החיבור הצליח!</h2>
                        <p>הפרטים נשמרו בהצלחה.</p>
                        <p>אפשר לסגור את הדף ולחזור לווצאפ.</p>
                    </div>
                </body>
                </html>
                """, 200
            return "Missing data", 400

        # WhatsApp Webhook
        data = request.get_json(silent=True) or {}

        if data and "entry" in data:
            entry = data.get("entry", [{}])[0]
            value = entry.get("changes", [{}])[0].get("value", {})
            messages = value.get("messages", [])
            if not messages: return "OK", 200

            msg = messages[0]
            sender, text = msg["from"], msg.get("text", {}).get("body", "").strip()
            print(f"MESSAGE from {sender}: '{text}'")

            if text.startswith("הגדר"):
                parts = text.split()
                if len(parts) >= 3:
                    set_user_credentials(sender, parts[2], parts[1])
                    send_wa(sender, "✅ הכל הוגדר בהצלחה! אני מחובר לנתונים שלך.")
                    return "OK", 200
                send_wa(sender, "⚠️ כדי להגדיר שלח: הגדר [ID] [KEY]\n(או פשוט שלח 'חבר' לקישור נוח)")
                return "OK", 200

            if "חבר" in text or "start" in text.lower():
                link = f"https://us-central1-sportruma.cloudfunctions.net/garmin-bot-v2/connect?state={sender}"
                send_wa(sender, f"הנה קישור נוח להזנת פרטי החיבור שלך:\n{link}")
                return "OK", 200

            if len(text) < 10 and text.startswith("i") and any(char.isdigit() for char in text):
                send_wa(sender, "נראה ששלחת לי Athlete ID. כדי להשלים את החיבור, שלח לי את ה-API Key שלך בפורמט הבא:\nהגדר " + text + " [API_KEY]")
                return "OK", 200

            try:
                intervals_data = fetch_intervals_data(sender)
                reply = get_ai_reply(text, intervals_data)
                send_wa(sender, reply)
            except Exception as e:
                if "User not connected" in str(e):
                    send_wa(sender, "היי! אני עדיין לא מכיר את המדדים שלך. שלח 'חבר' כדי להתחבר ל-Intervals.icu.")
                else:
                    print(f"ERROR: {e}")
                    send_wa(sender, "מצטער, יש לי תקלה קלה בגישה לנתונים. נסה שוב בעוד דקה.")

        return "OK", 200
    except Exception as e:
        print(f"GLOBAL ERROR: {e}")
        return "OK", 200
