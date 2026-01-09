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

def download_wa_media(media_id):
    """מוריד קובץ מדיה (אודיו) מוואטסאפ ומחזיר את הביטים שלו."""
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}
    try:
        # 1. קבלת URL להורדה
        res = requests.get(f"https://graph.facebook.com/v21.0/{media_id}", headers=headers, timeout=10)
        if res.status_code != 200: return None
        download_url = res.json().get("url")
        
        # 2. הורדת הקובץ בפועל
        res = requests.get(download_url, headers=headers, timeout=15)
        if res.status_code == 200:
            return res.content
    except Exception as e:
        print(f"Error downloading media: {e}")
    return None

def send_wa(to, body):
    to_clean = _clean_id(to)
    # הגנה מפני הודעה ריקה או לא תקינה
    body_str = str(body) if body else "אני מעבד את הנתונים..."
    print(f"SENDING WA to {to_clean}: {body_str[:50]}...")
    try:
        res = requests.post(
            f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages",
            json={"messaging_product": "whatsapp", "to": to_clean, "type": "text", "text": {"body": body_str}},
            headers={"Authorization": f"Bearer {WA_TOKEN}"}, timeout=10
        )
        print(f"WA STATUS: {res.status_code}, RESPONSE: {res.text}")
    except Exception as e:
        print(f"Error sending WA: {e}")

def get_user_doc(user_id):
    return db.collection("users").document(_clean_id(user_id)).get().to_dict() or {}

def set_user_credentials(user_id, api_key, athlete_id, name=None, emergency_name=None, emergency_phone=None):
    # ניקוי יסודי - לוקחים רק את המילה הראשונה ומנקים תווים לא רצויים
    clean_key = _first_word(api_key)
    clean_id = _first_word(athlete_id)
    doc_id = _clean_id(user_id)
    
    data = {
        "intervals_api_key": clean_key,
        "intervals_athlete_id": clean_id,
        "connected_at": firestore.SERVER_TIMESTAMP
    }
    if name: data["name"] = name.strip()
    if emergency_name: data["emergency_name"] = emergency_name.strip()
    if emergency_phone: data["emergency_phone"] = _clean_id(emergency_phone)
    
    print(f"SAVING CREDENTIALS: user_id={user_id}, athlete_id={clean_id}, emergency={emergency_name}")
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
        # הוספת טווח תאריכים למניעת שגיאת 422
        res = requests.get(url, auth=auth, params={'oldest': oldest, 'newest': newest, 'limit': 1}, timeout=15)
        print(f"DEBUG: Activities status: {res.status_code}")
        if res.status_code == 200:
            acts = res.json()
            if acts and isinstance(acts, list) and len(acts) > 0: 
                last_activity = acts[0]
                print(f"DEBUG: Found last activity: {last_activity.get('name')}")
        else:
            print(f"DEBUG: Activities error response: {res.text}")
    except Exception as e:
        print(f"DEBUG: Activities exception: {e}")

    today_str = datetime.date.today().isoformat()
    dismissed = user_doc.get("intervention_dismissed_at") == today_str

    return {
        "user_name": user_doc.get("name", "חבר"),
        "emergency_name": user_doc.get("emergency_name"),
        "emergency_phone": user_doc.get("emergency_phone"),
        "intervention_dismissed": dismissed,
        "hrv": wellness.get("hrv", "N/A"),
        "resting_hr": wellness.get("restingHR", "N/A"),
        "stress": wellness.get("stressScore", "N/A"),
        "sleep": round(wellness.get("sleepSecs", 0) / 3600, 1) if wellness.get("sleepSecs") else "N/A",
        "last_activity": last_activity,
        "date_found": wellness.get("id", "No recent data found"),
        "history": history_list
    }

# --- AI LOGIC ---
def get_ai_reply(text, data, mode="chat", audio_bytes=None):
    # הכנת מידע על הפעילות האחרונה
    last_act = data.get('last_activity')
    act_info = "No recent activities found"
    if last_act:
        act_info = f"{last_act.get('name')} ({last_act.get('type')}) on {last_act.get('start_date_local')}. Duration: {round(last_act.get('moving_time',0)/60)} min, Distance: {round(last_act.get('distance',0)/1000, 1)} km"

    # הכנת היסטוריה למודל
    history_str = ""
    history_data = data.get('history', [])
    for h in history_data:
        history_str += f"- Date {h.get('id')}: HRV {h.get('hrv', 'N/A')}, RHR {h.get('restingHR', 'N/A')}, Sleep {round(h.get('sleepSecs',0)/3600,1) if h.get('sleepSecs') else 'N/A'}h\n"

    # קטלוג אימונים מלא ומפורט
    workout_protocol = """
    ## Nervous System Regulation Library:
    1. Hyperarousal/Fight (High stress, anxiety, High RHR): 
       - Goal: Grounding and soothing.
       - Recommendation: Grounding Yoga or 4-7-8 Breathing.
    
    2. Freeze (Stuck energy, numbness, Low HRV):
       - Goal: Building agency and internal power.
       - Recommendation: Bodyweight Strength (Squats/Planks) or Power Yoga.
    
    3. Collapse (Extreme fatigue, shutdown, Low energy):
       - Goal: Rhythmic activation and gentle waking.
       - Recommendation: Seated Pilates or Rhythmic Step Aerobics.

    4. Safety/Flow (Balanced metrics, Good HRV, Normal RHR):
       - Goal: Building resilience and enjoying high energy.
       - Recommendation: HIIT workout, Running, or a dynamic Strength session.
    """

    # תפריט התערבות (Intervention Menu)
    emergency_name = data.get('emergency_name')
    emergency_option = f"\n• *עזרה*: שליחת הודעה ל{emergency_name} (כתוב 'עזרה')." if emergency_name else ""
    
    intervention_menu = f"""
--- *תפריט עזרה (Intervention)* ---
אני מזהה עומס במערכת. בוא/י נבחר עוגן:
• *נשימה*: תרגיל 4-7-8 (כתוב 'נשימה').
• *קרקוע*: תרגיל 5-4-3-2-1 (כתוב 'קרקוע').
• *תנועה*: אימון ויסות (כתוב 'אימון').{emergency_option}
• *הכל בסדר*: אני מרגיש/ה יותר טוב (כתוב 'בסדר').
    """

    # ניתוח פיזיולוגי מבוסס מחקר (Clinical Logic)
    clinical_logic = """
    1. HRV Baseline Analysis: 
       - A drop of >15% from the 10-day average indicates Sympathetic Overload/Distress.
       - Stable high HRV indicates Vagal Tone/Safety.
    2. RHR (Resting Heart Rate):
       - Elevation of >5 bpm above baseline suggests Hyperarousal or systemic stress.
       - High nocturnal RHR is a strong 'Trauma Signature'.
    3. Polyvagal States:
       - Fight/Flight: High RHR + Low HRV.
       - Freeze: Stable RHR + Extremely Low HRV + Numbness.
       - Collapse/Hypoarousal: Low RHR + Low HRV + Fatigue.
    """

    # הגדרת משימה לפי מצב
    is_dismissed = data.get('intervention_dismissed', False)
    
    if mode == "morning_analysis":
        task_desc = f"""
        Mode 1: Morning Analysis (09:00 AM).
        Analyze the last 14 days vs today. Identify Polyvagal state.
        IMPORTANT: If state is complex (Hyperarousal/Freeze) AND intervention_dismissed is False, show the Menu:
        {intervention_menu}
        """
    elif mode == "evening_wind_down":
        task_desc = f"""
        Mode 2: Evening Wind-down (09:00 PM).
        If stress is high AND intervention_dismissed is False, show the Menu:
        {intervention_menu}
        """
    else:
        task_desc = f"""
        Standard Chat Mode.
        If the user says "בסדר" or "הכל טוב", acknowledge it warmly.
        ONLY show the Intervention Menu if you detect NEW distress OR if explicitly asked for help.
        If intervention_dismissed is True, AVOID showing the menu.
        """

    prompt = f"""
    Role: אסיסטנט חכם, אנושי ורגיש בשם Deep-Rest Guard.
    
    DATA FOR ANALYSIS (Only if relevant):
    - Today: HRV {data.get('hrv', 'N/A')}, RHR {data.get('resting_hr', 'N/A')}, Sleep {data.get('sleep', 'N/A')}h.
    - Last Activity: {act_info}
    - History: {history_str}
    
    Instructions:
    1. PRIORITY - ACTION KEYWORDS: 
       - If message is "נשימה": Give clear, step-by-step 4-7-8 breathing instructions.
       - If message is "קרקוע": Lead a 5-4-3-2-1 grounding exercise (5 things to see, 4 to touch, 3 to hear, 2 to smell, 1 to taste).
       - If message is "אימון": 
         1. Choose the best workout from the Regulation Library based on their metrics.
         2. Give CLEAR, step-by-step instructions on how to perform the workout.
         3. Explain briefly HOW it helps their current state.
       - **In these cases, SKIP the metrics analysis and focus ONLY on the instructions and support.**
    
    2. STANDARD ANALYSIS (If no action keyword):
       - Address the user by name: "היי {data.get('user_name', 'חבר')} 🤍".
       - Compare today's metrics to history. Be insightful (e.g., "ה-HRV שלך ירד ב-15%").
       - Give 1-2 practical tips for improvement.
       - Offer the menu if distress is detected:
{intervention_menu}
    
    3. TONE: Warm, helpful, and human. 4-6 sentences. 
       - USE EMOJIS naturally to fit the mood (e.g., 🤍, ✨, 🧘, ⚓, 📈).
       - Make the user feel supported and seen.
    
    Context: {task_desc}
    Workout Protocol: {workout_protocol}
    
    User Message: "{text if text else '[Voice Note]'}"
    JSON Output Format: {{ "reply": "YOUR_MESSAGE_HERE" }}
    """
    
    contents = [prompt]
    if audio_bytes:
        contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"))

    try:
        res = ai_client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        ai_reply = json.loads(res.text).get("reply")
        if not ai_reply:
            return f"היי {data.get('user_name', 'חבר')}, אני כאן איתך. איך אוכל לעזור? ✨"
        return str(ai_reply)
    except Exception as e:
        print(f"AI ERROR: {e}")
        return "היי, אני מעבד את הנתונים, מיד אענה. ✨"

# --- MAIN HANDLER ---
@functions_framework.http
def whatsapp_bot(request):
    print("=== FUNCTION STARTED ===")
    
    # Handle Scheduled Tasks (Morning/Evening)
    task = request.args.get("task")
    if task:
        users = db.collection("users").get()
        for user_doc in users:
            u_id = user_doc.id
            u_data = user_doc.to_dict()
            name = u_data.get("name", "חבר")
            if task == "morning":
                morning_msg = f"""
היי {name} 🤍 בוקר טוב ✨

איך עבר עליך הלילה? 🌿
כדי שנתחיל את היום יחד, אשמח שתענה/י על 3 שאלות קצרות (1-5):
1. איך הייתה איכות השינה שלך? 😴
2. כמה אנרגיה יש לך הבוקר? ⚡
3. מה רמת הדריכות/מתח בגוף? ⚓

בנוסף, בצע/י סנכרון קצר עם השעון וכתוב/כתבי לי 'בוצע' כשסיימת. 🧘
                """
                send_wa(u_id, morning_msg.strip())
            elif task == "evening":
                send_wa(u_id, f"ערב טוב {name} 🌙\nזה הזמן שלנו להתחיל להוריד הילוך לקראת השינה. ✨\nאיך רמת המתח שלך כרגע מ-1 (רגוע) ועד 5 (דרוך מאוד)? ⚓")
        return "Tasks triggered", 200

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
                        <div style="margin-top: 20px; border-top: 1px solid #eee; padding-top: 10px;">
                            <p style="font-size: 14px; color: #666;"><b>איש קשר לחירום (אופציונלי):</b></p>
                            <input name="emergency_name" placeholder="שם איש הקשר">
                            <input name="emergency_phone" placeholder="מספר טלפון (למשל 0501234567)">
                        </div>
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
            emergency_name = request.form.get("emergency_name")
            emergency_phone = request.form.get("emergency_phone")
            
            if phone and api_key and athlete_id:
                set_user_credentials(phone, api_key, athlete_id, user_name, emergency_name, emergency_phone)
                u_name = user_name.strip() if user_name else "חבר"
                welcome_msg = f"✅ היי {u_name} 🤍, החיבור הצליח!\nאני מתחיל לעקוב אחר המדדים שלך ולשמור עליך. ✨"
                send_wa(phone, welcome_msg)
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
            sender = msg["from"]
            msg_type = msg.get("type")
            text = msg.get("text", {}).get("body", "").strip()
            audio_bytes = None

            print(f"MESSAGE from {sender} (type: {msg_type}): '{text}'")

            user_doc = get_user_doc(sender)

            # --- Handle Voice Notes ---
            if msg_type == "audio" or msg_type == "voice":
                media_id = msg.get("audio", {}).get("id") or msg.get("voice", {}).get("id")
                if media_id:
                    print(f"Downloading voice note {media_id}...")
                    audio_bytes = download_wa_media(media_id)
                    text = "[הודעה קולית]"

            # --- Intervention Protocol: Emergency Contact ---
            if "עזרה" in text or "עזרי" in text:
                e_name = user_doc.get("emergency_name")
                e_phone = user_doc.get("emergency_phone")
                u_name = user_doc.get("name", "חבר")
                
                if e_phone:
                    alert_msg = f"⚓ הודעה מ-Deep-Rest Guard: {u_name} ביקש/ה לעדכן אותך שהוא/היא נמצא/ת ברגע של עומס רגשי וזקוק/ה לתמיכה. כדאי ליצור קשר בהקדם. 🤍"
                    send_wa(e_phone, alert_msg)
                    send_wa(sender, f"היי {u_name}, שלחתי הודעת עדכון ל{e_name} ✨ אני כאן איתך עד שהם יענו. בוא ניקח נשימה עמוקה יחד. 🧘")
                    return "OK", 200
                else:
                    send_wa(sender, f"היי {u_name}, לא הגדרת איש קשר לחירום. 🌿 שלח 'חבר' כדי שנוכל לעדכן את הפרטים יחד.")
                    return "OK", 200

            # --- Logic for Protocol 2.0 Keywords ---
            # 0. Dismiss Intervention
            if any(word in text for word in ["בסדר", "הכל טוב", "אני בסדר"]):
                db.collection("users").document(_clean_id(sender)).set({
                    "intervention_dismissed_at": datetime.date.today().isoformat()
                }, merge=True)
                u_name = user_doc.get("name", "חבר")
                send_wa(sender, f"שמח לשמוע שאת/ה מרגיש/ה יותר טוב, {u_name} 🤍 אני כאן אם תצטרך/י משהו נוסף. ✨")
                return "OK", 200

            # 1. Morning "Done" (בוצע)
            if "בוצע" in text:
                try:
                    intervals_data = fetch_intervals_data(sender)
                    reply = get_ai_reply(text, intervals_data, mode="morning_analysis")
                    send_wa(sender, reply)
                    return "OK", 200
                except Exception as e:
                    print(f"Morning Error: {e}")
                    u_name = user_doc.get("name", "חבר")
                    send_wa(sender, f"היי {u_name} 🤍, יש עיכוב קטן בנתונים. נסה/י שוב בעוד דקה. ✨")
                    return "OK", 200

            # 2. Evening Stress Level (1-5)
            if text in ["1", "2", "3", "4", "5"]:
                try:
                    intervals_data = fetch_intervals_data(sender)
                    reply = get_ai_reply(f"רמת המתח שלי היא {text}", intervals_data, mode="evening_wind_down")
                    send_wa(sender, reply)
                    return "OK", 200
                except:
                    # Even if intervals fails, we want to respond to the stress level
                    dummy_data = {"user_name": get_user_doc(sender).get("name", "חבר")}
                    reply = get_ai_reply(f"רמת המתח שלי היא {text}", dummy_data, mode="evening_wind_down")
                    send_wa(sender, reply)
                    return "OK", 200
            
            # --- Standard Bot Logic ---
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
                # Pass full user doc to ensure name and emergency info are available
                reply = get_ai_reply(text, intervals_data, audio_bytes=audio_bytes)
                send_wa(sender, reply)
            except Exception as e:
                if "User not connected" in str(e):
                    send_wa(sender, f"היי {user_doc.get('name', 'חבר')}, אני עדיין לא מכיר את המדדים שלך. ✨ שלח 'חבר' כדי שנתחבר יחד.")
                else:
                    print(f"ERROR: {e}")
                    # Try to reply even without intervals data if possible
                    dummy_data = {"user_name": user_doc.get("name", "חבר"), "emergency_name": user_doc.get("emergency_name")}
                    reply = get_ai_reply(text, dummy_data, audio_bytes=audio_bytes)
                    send_wa(sender, reply)

        return "OK", 200
    except Exception as e:
        print(f"GLOBAL ERROR: {e}")
        return "OK", 200
