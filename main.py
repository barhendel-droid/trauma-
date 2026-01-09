import datetime
import json
import requests
import firebase_admin
from firebase_admin import firestore
import functions_framework
from google import genai
from google.genai import types

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO

plt.switch_backend('Agg') # Ensure stability in serverless environments

# --- CONFIGURATION ---
GEMINI_API_KEY = "AIzaSyBcDMlrAkg48nnL8Wy8fHlNm18jjm5yR3c"
WA_TOKEN = "EAAMTn8rGplIBQRiwj4mH9Ck7KlpIVkIRYxxpElLUDtvqLRdcbZBHvyaRIBxDi9RZAtYXGgZAZBAYiTR5oNPENCcB9YVZBZAdocseTHxNwoymB08UM4Ml6c1uRZCpuBQZC5iWL6liod7wdZCEkFCHVkSWDn06rqHS2PXXGQsShgSOGLkcAN6JiaHvkqmPSddE3AxOXSYl5Uktt7unhP6u91vqZCs74hxXQPLXXGZAN1DTNJy"
PHONE_NUMBER_ID = "875111485694772"
VERIFY_TOKEN = "MYSUPERSECRET"

PCL5_QUESTIONS = [
    "איך המצב רוח שלך היום? 😊",
    "איך רמת האנרגיה שלך? ⚡",
    "איך ישנת הלילה? 😴",
    "איך מזג האוויר הפנימי שלך כרגע? (סוער ⛈️ / מעורפל 🌫️ / שקט ☀️)"
]

PCL5_OPTIONS = [
    {"id": "1", "title": "1 - גרוע / סוער מאוד ⛈️"},
    {"id": "2", "title": "2 - לא משהו / מעורפל 🌫️"},
    {"id": "3", "title": "3 - סביר / ככה ככה 🌤️"},
    {"id": "4", "title": "4 - טוב / בהיר ☀️"},
    {"id": "5", "title": "5 - מצוין / שקט ורגוע ✨"}
]

# --- INIT ---
if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- HELPERS ---
def _clean_id(user_id):
    if not user_id: return ""
    return str(user_id).replace("@g.us", "").replace("@s.whatsapp.net", "").strip()

def is_group(chat_id):
    return "@g.us" in str(chat_id) or "-" in str(chat_id)

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

def send_wa(to, body, interactive_list=None):
    to_clean = _clean_id(to)
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    
    if interactive_list:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_clean,
            "type": "interactive",
            "interactive": interactive_list
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": to_clean,
            "type": "text",
            "text": {"body": str(body) if body else "..."}
        }
        
    print(f"SENDING WA to {to_clean}...")
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"WA STATUS: {res.status_code}")
    except Exception as e:
        print(f"Error sending WA: {e}")

def send_wa_poll(to, question, options):
    """Sends a poll-like interactive list message (Cloud API stable version)."""
    to_clean = _clean_id(to)
    
    # Map options to the interactive list format
    rows = []
    for opt in options:
        rows.append({
            "id": f"poll_ans_{opt['id']}",
            "title": opt['title'], # Fixed: used 'title' instead of 'label'
            "description": "לחץ לבחירה"
        })
        
    interactive_list = {
        "type": "list",
        "header": {"type": "text", "text": "רגע של כנות ✨"},
        "body": {"text": question[:1024]},
        "footer": {"text": "בחר/י את התשובה המתאימה ביותר"},
        "action": {
            "button": "בחר תשובה",
            "sections": [
                {
                    "title": "אפשרויות",
                    "rows": rows
                }
            ]
        }
    }
    
    send_wa(to_clean, question, interactive_list=interactive_list)

def send_wa_location(to, lat, lon, name="", address=""):
    """שולחת הודעת מיקום למשתמש."""
    to_clean = _clean_id(to)
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "location",
        "location": {
            "longitude": lon,
            "latitude": lat,
            "name": name,
            "address": address
        }
    }
    try:
        res = requests.post(
            f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Send location status: {res.status_code}")
    except Exception as e:
        print(f"Error sending location: {e}")

def send_wa_audio(to, media_id):
    """שולחת הודעת קול למשתמש."""
    to_clean = _clean_id(to)
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "audio",
        "audio": {"id": media_id}
    }
    try:
        res = requests.post(
            f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Send audio status: {res.status_code}")
    except Exception as e:
        print(f"Error sending audio: {e}")

def upload_wa_media(file_bytes, file_name, mime_type):
    """מעלה קובץ לווטסאפ ומחזיר את ה-media_id."""
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}
    files = {
        "file": (file_name, file_bytes, mime_type),
        "messaging_product": (None, "whatsapp")
    }
    try:
        res = requests.post(
            f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/media",
            headers=headers,
            files=files,
            timeout=20
        )
        if res.status_code == 200:
            return res.json().get("id")
        print(f"Media upload failed: {res.text}")
    except Exception as e:
        print(f"Error uploading media: {e}")
    return None

def send_wa_image(to, media_id, caption=""):
    """שולחת תמונה למשתמש לפי media_id."""
    to_clean = _clean_id(to)
    headers = {"Authorization": f"Bearer {WA_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to_clean,
        "type": "image",
        "image": {"id": media_id, "caption": caption}
    }
    try:
        res = requests.post(
            f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"Send image status: {res.status_code}")
    except Exception as e:
        print(f"Error sending image: {e}")

def get_graph_menu():
    return {
        "type": "list",
        "header": {"type": "text", "text": "דוח התקדמות ויזואלי 📈"},
        "body": {"text": "בחר את טווח הזמן שברצונך לראות בגרף:"},
        "footer": {"text": "Deep-Rest Guard"},
        "action": {
            "button": "בחר טווח זמן",
            "sections": [
                {
                    "title": "טווח תצוגה",
                    "rows": [
                        {"id": "graph_3", "title": "📊 גרף יומי", "description": "3 הימים האחרונים"},
                        {"id": "graph_7", "title": "📈 גרף שבועי", "description": "7 הימים האחרונים"},
                        {"id": "graph_30", "title": "📅 גרף חודשי", "description": "30 הימים האחרונים"}
                    ]
                }
            ]
        }
    }

def generate_progress_graph(user_id, days=14):
    """מייצרת גרף התקדמות ושולחת אותו כתמונה."""
    doc_id = _clean_id(user_id)
    user_doc = get_user_doc(user_id)
    user_name = user_doc.get("name", "User")
    
    history_docs = db.collection("users").document(doc_id).collection("wellness_history")\
        .order_by("id", direction=firestore.Query.DESCENDING).limit(days).get()
    
    data_list = [d.to_dict() for d in history_docs]
    if not data_list: return None
    
    df = pd.DataFrame(data_list)
    df['date'] = pd.to_datetime(df['id'])
    df = df.sort_values('date')
    
    # Normalize data for plotting on the same graph
    # Sleep: 7h -> 70
    df['sleep_plot'] = df.get('sleepSecs', pd.Series([0]*len(df))).fillna(0) / 360 
    
    # HRV: Look for any available HRV metric (consistent key first, then fallbacks)
    possible_hrv_cols = ['hrv_consistent', 'hrv', 'hrv_sdnn', 'rmssd']
    df['hrv_plot'] = np.nan
    for col in possible_hrv_cols:
        if col in df.columns:
            # Ensure numeric conversion
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df['hrv_plot'] = df['hrv_plot'].fillna(df[col])
    
    # Energy: 1-5 -> 20-100
    df['energy_plot'] = pd.to_numeric(df.get('survey_1', pd.Series([np.nan]*len(df))), errors='coerce').fillna(0) * 20

    # Load: Scale down if very high to keep proportions
    raw_load = pd.to_numeric(df.get('training_load', pd.Series([0]*len(df))), errors='coerce').fillna(0)
    max_load = raw_load.max()
    load_label = 'Training Load'
    if max_load > 150:
        df['load_plot'] = raw_load / 2
        load_label = 'Training Load (scaled /2)'
    else:
        df['load_plot'] = raw_load

    # Use a cleaner style
    plt.figure(figsize=(10, 6))
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # Plot HRV only where it's > 0
    hrv_data = df[df['hrv_plot'] > 0]
    if not hrv_data.empty:
        plt.plot(hrv_data['date'], hrv_data['hrv_plot'], marker='o', label='Recovery (HRV)', color='#2ecc71', linewidth=2.5)
    
    # Plot Sleep
    plt.plot(df['date'], df['sleep_plot'], marker='s', label='Sleep Quality (scaled)', color='#3498db', linewidth=2.5)
    
    # Plot Energy
    energy_data = df[df['energy_plot'] > 0]
    if not energy_data.empty:
        plt.plot(energy_data['date'], energy_data['energy_plot'], marker='D', label='Energy Level (1-5)', color='#9b59b6', linewidth=2.5)
    
    # Plot Load
    plt.plot(df['date'], df['load_plot'], marker='^', label=load_label, color='#e74c3c', linestyle=':', linewidth=2)
    
    plt.title('Your Progress Report', fontsize=18, pad=20, fontweight='bold')
    plt.xlabel('Date', fontsize=12, fontweight='bold')
    plt.ylabel('Normalized Scale (0-120)', fontsize=12, fontweight='bold')
    plt.legend(loc='upper left', frameon=True, shadow=True, fontsize=10)
    
    # Better date formatting
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.xticks(rotation=45)
    
    # Set Y axis to show a consistent range
    plt.ylim(0, 130) 
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=120)
    plt.close()
    return buf.getvalue()

def generate_weekly_report(user_id):
    doc_id = _clean_id(user_id)
    history_docs = db.collection("users").document(doc_id).collection("wellness_history")\
        .order_by("id", direction=firestore.Query.DESCENDING).limit(14).get()
    
    history = [d.to_dict() for d in history_docs]
    if len(history) < 3: return None
    
    this_week = history[:7]
    last_week = history[7:14] if len(history) >= 7 else []
    
    def avg(lst, key):
        vals = [item.get(key) for item in lst if item.get(key) and isinstance(item.get(key), (int, float))]
        return sum(vals) / len(vals) if vals else None

    hrv_now = avg(this_week, "hrv") or avg(this_week, "hrv_sdnn")
    hrv_prev = avg(last_week, "hrv") or avg(last_week, "hrv_sdnn")
    sleep_now = avg(this_week, "sleepSecs")
    
    # Survey averages (Mood and Energy)
    mood_avg = avg(this_week, "survey_0")
    energy_avg = avg(this_week, "survey_1")

    report = "📊 *סיכום חוסן שבועי* ⚓\n\n"
    
    if hrv_now:
        diff = round(((hrv_now - hrv_prev) / hrv_prev * 100)) if (hrv_prev and hrv_prev > 0) else 0
        emoji = "📈" if diff >= 0 else "📉"
        report += f"{emoji} *חוסן גופני (HRV):* {round(hrv_now)} ({diff}% שבוע שעבר)\n"
    
    if sleep_now:
        report += f"😴 *ממוצע שינה:* {round(sleep_now / 3600, 1)} שעות\n"
        
    if mood_avg and energy_avg:
        # Calculate a simple "Mental Balance" score out of 100
        mental_score = round(((mood_avg + energy_avg) / 10) * 100)
        report += f"🧠 *איזון רגשי:* {mental_score}/100 (לפי הדיווחים שלך)\n"

    report += "\n💡 *תובנה לשבוע הקרוב:* "
    if hrv_now and hrv_prev and hrv_now < hrv_prev:
        report += "הגוף שלך תחת עומס. נסה/י לתעדף שינה והורדת עצימות. 🌿"
    elif mood_avg and mood_avg < 3:
        report += "נראה שעבר עליך שבוע רגשי לא פשוט. אנחנו כאן כדי להקשיב. 🤍"
    else:
        report += "את/ה בנתיב הנכון! המערכת שלך מאוזנת וחזקה. ✨"
        
    return report

def get_emergency_list(body_text="בחר/י את האופציה המתאימה לך כרגע:", emergency_name=None):
    rows = [
        {"id": "action_breath", "title": "🧘 תרגיל נשימה", "description": "נשימת 4-7-8 להרגעה"},
        {"id": "action_ground", "title": "⚓ תרגיל קרקוע", "description": "טכניקת 5-4-3-2-1"},
        {"id": "action_workout", "title": "💪 אימון מותאם", "description": "אימון לפי המדדים שלך"},
        {"id": "action_community", "title": "🤝 הקהילה שלנו", "description": "מה קורה בקהילה שלנו"},
        {"id": "action_fine", "title": "✅ הכל בסדר", "description": "אני מרגיש/ה יותר טוב"}
    ]
    
    if emergency_name:
        rows.insert(3, {"id": "action_help_contact", "title": f"🆘 הודעה ל{emergency_name}", "description": "שליחת בקשת עזרה דחופה"})

    return {
        "type": "list",
        "header": {"type": "text", "text": "כלים לוויסות וסיוע ⚓"},
        "body": {"text": body_text[:1024]}, # WhatsApp limits body to 1024 chars
        "footer": {"text": "Deep-Rest Guard 🤍"},
        "action": {
            "button": "אפשרויות סיוע",
            "sections": [
                {
                    "title": "כלים לוויסות",
                    "rows": rows
                },
                {
                    "title": "מוקדי סיוע חיצוניים",
                    "rows": [
                        {"id": "help_nefesh", "title": "🛑 מוקד נפש אחת", "description": "*8944 - משרד הביטחון"},
                        {"id": "help_natal", "title": "❤️ מוקד נט\"ל", "description": "1-800-363-363 - טראומה"},
                        {"id": "help_eran", "title": "👂 מוקד ער\"ן", "description": "1201 - עזרה ראשונה נפשית"},
                        {"id": "help_sahar", "title": "💬 מוקד סה\"ר", "description": "055-957-1399 - בוואטסאפ"}
                    ]
                }
            ]
        }
    }

def get_community_menu():
    """Returns a menu for community features."""
    return {
        "type": "list",
        "header": {"type": "text", "text": "הקהילה שלנו 🤝"},
        "body": {"text": "כאן אפשר לראות מה קורה בקהילה, למצוא שותף/ה או להצטרף לקבוצה:"},
        "footer": {"text": "Deep-Rest Guard"},
        "action": {
            "button": "בחר אפשרות",
            "sections": [
                {
                    "title": "הקהילה שלי",
                    "rows": [
                        {"id": "comm_stats", "title": "📊 כמה תרגלנו היום?", "description": "סטטיסטיקה קבוצתית אנונימית"},
                        {"id": "comm_join_group", "title": "📢 הצטרפות לקבוצה", "description": "מעבר לקבוצת הקהילה בוואטסאפ"},
                        {"id": "comm_find_partner", "title": "🤝 חפש שותף/ה", "description": "חיבור למשתמש אחר לשיחה או אימון"},
                        {"id": "comm_opt_out", "title": "🔕 הפסקת זמינות", "description": "הסרת הפרופיל מחיפוש שותפים"}
                    ]
                }
            ]
        }
    }

def find_community_partner(sender_id):
    """Finds a random partner who opted-in, excluding the sender."""
    query = db.collection("users").where("partner_opt_in", "==", True).limit(10).get()
    potential_partners = [u for u in query if u.id != _clean_id(sender_id)]
    if not potential_partners: return None
    import random
    return random.choice(potential_partners).to_dict(), random.choice(potential_partners).id

def log_community_action(user_id, action_type):
    """Logs a specific regulation action with a timestamp."""
    db.collection("community_actions").add({
        "user_id": _clean_id(user_id),
        "action": action_type,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

def get_community_message(u_name):
    """Generates a community message based on actions in the last 24 hours."""
    now = datetime.datetime.now(datetime.timezone.utc)
    yesterday = now - datetime.timedelta(hours=24)
    
    # Query actions in the last 24h
    actions_ref = db.collection("community_actions").where("timestamp", ">", yesterday).get()
    actions_count = len(actions_ref)
    
    # Count unique active users in last 24h
    active_users = set()
    for doc in actions_ref:
        active_users.add(doc.to_dict().get("user_id"))
    
    users_count = len(active_users)
    if users_count == 0:
        users_count = len(db.collection("users").get()) # Fallback to total users
        
    minutes = actions_count * 5 # Estimate 5 mins per action
    
    return f"היי {u_name}, את/ה לא לבד. 🤍\n\nב-24 השעות האחרונות, בקהילה שלנו היו *{users_count} חברים* פעילים. יחד איתך, נעשו *{actions_count} תרגולים*, שהם בערך *{minutes} דקות* של שקט. ✨\n\nכל פעם שאת/ה מתרגל/ת, זה חלק מהמאמץ של כולנו. טוב שאת/ה כאן! ⚓"

def get_user_doc(user_id):
    return db.collection("users").document(_clean_id(user_id)).get().to_dict() or {}

def set_user_credentials(user_id, api_key, athlete_id, name=None, emergency_name=None, emergency_phone=None, gender=None):
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
    if gender: data["gender"] = gender
    
    print(f"SAVING CREDENTIALS: user_id={user_id}, athlete_id={clean_id}, gender={gender}")
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
                # Normalize HRV key BEFORE saving to history
                hrv_val = entry.get("hrv") or entry.get("hrv_sdnn") or entry.get("rmssd")
                if hrv_val: entry["hrv_consistent"] = hrv_val
                
                # Store in history subcollection
                hist_ref = db.collection("users").document(doc_id).collection("wellness_history").document(str(entry_id))
                batch.set(hist_ref, entry, merge=True)
            
            # Check for latest valid record
            hrv_val = entry.get("hrv_consistent")
            rhr_val = entry.get("restingHR") or entry.get("resting_hr")
            if hrv_val or rhr_val:
                wellness = entry
        batch.commit()
        print(f"DEBUG: Saved {len(wellness_data)} entries to history for {doc_id}")
    
    # Fetch some history for trend analysis
    history_docs = db.collection("users").document(doc_id).collection("wellness_history")\
        .order_by("id", direction=firestore.Query.DESCENDING).limit(10).get()
    history_list = [d.to_dict() for d in history_docs]

    # Aggregate survey data for AI context
    def avg_s(key):
        vals = [h.get(key) for h in history_list if h.get(key)]
        return round(sum(vals)/len(vals), 1) if vals else "N/A"
    
    survey_context = {
        "avg_mood": avg_s("survey_0"),
        "avg_energy": avg_s("survey_1"),
        "avg_weather": avg_s("survey_3")
    }

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

    # Gender labels
    g = user_doc.get("gender", "male")
    u_name = user_doc.get("name", "חבר")
    
    # Simple gender helper for Hebrew strings
    def t(m, f): return f if g == "female" else m

    return {
        "user_name": u_name,
        "gender": g,
        "emergency_name": user_doc.get("emergency_name"),
        "emergency_phone": user_doc.get("emergency_phone"),
        "intervention_dismissed": dismissed,
        "hrv": wellness.get("hrv_consistent", "N/A"),
        "resting_hr": wellness.get("restingHR", "N/A"),
        "stress": wellness.get("stressScore", "N/A"),
        "sleep": round(wellness.get("sleepSecs", 0) / 3600, 1) if wellness.get("sleepSecs") else "N/A",
        "last_activity": last_activity,
        "date_found": wellness.get("id", "No recent data found"),
        "history": history_list,
        "survey_context": survey_context
    }

# --- AI LOGIC ---
def get_group_pulse(group_id):
    """Calculates anonymized group averages for today."""
    members = db.collection("users").where("group_id", "==", group_id).get()
    moods = []
    energies = []
    
    today_str = datetime.date.today().isoformat()
    for m in members:
        # Check today's wellness history for each member
        hist = db.collection("users").document(m.id).collection("wellness_history").document(today_id).get()
        if hist.exists:
            d = hist.to_dict()
            if "survey_0" in d: moods.append(d["survey_0"])
            if "survey_1" in d: energies.append(d["survey_1"])
            
    if not moods: return None
    
    avg_mood = sum(moods) / len(moods)
    avg_energy = sum(energies) / len(energies)
    
    weather = "שקט ☀️" if avg_mood > 4 else "מעורפל 🌫️" if avg_mood > 2.5 else "סוער ⛈️"
    
    return f"🌊 *דופק קבוצתי יומי* ⚓\n\nמדד האנרגיה הממוצע שלנו: {round(avg_energy, 1)}/5\nמזג האוויר הפנימי המשותף: {weather}\n\nזה זמן מצוין לקחת רגע לנשימה משותפת. אתם לא לבד. 🤍"

def notify_admin_if_needed(user_id, data):
    """Notifies group admin if a user shows extreme distress."""
    user_doc = db.collection("users").document(_clean_id(user_id)).get().to_dict() or {}
    group_id = user_doc.get("group_id")
    if not group_id: return
    
    group_doc = db.collection("groups").document(group_id).get().to_dict() or {}
    admin_phone = group_doc.get("admin_phone")
    if not admin_phone: return
    
    # Distress Criteria: Mood = 1 OR HRV drop > 30%
    mood = user_doc.get("pcl5_responses", {}).get("0") # Mood is first question
    hrv = data.get("hrv")
    
    if mood == "1" or (isinstance(hrv, (int, float)) and hrv < 20):
        alert = f"⚠️ *התראת חוסן למנהל* ⚠️\n\nהמשתמש {user_doc.get('name')} בסיכון או הצפה.\nמדד HRV: {hrv}\nדיווח מצב רוח: 1/5\n\nכדאי ליצור קשר אישי בהקדם. ✨"
        send_wa(admin_phone, alert)

def get_ai_reply(text, data, mode="chat", audio_bytes=None, is_group_msg=False):
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

    # תפריט התערבות (Intervention Menu) - Removed text-based menu as we now use interactive list
    
    # ניתוח פיזיולוגי מבוסס מחקר (Clinical Logic)
    clinical_logic = """
    1. HRV Baseline Analysis: 
       - A drop of >15% from the 10-day average indicates Sympathetic Overload/Distress.
       - Stable high HRV indicates Vagal Tone/Safety.
    2. RHR (Resting Heart Rate):
       - Elevation of >5 bpm above baseline suggests Hyperarousal or systemic stress.
    3. Polyvagal States:
       - Fight/Flight: High RHR + Low HRV.
       - Freeze: Stable RHR + Extremely Low HRV + Numbness.
       - Collapse/Hypoarousal: Low RHR + Low HRV + Fatigue.
    """

    # הגדרת משימה לפי מצב
    is_dismissed = data.get('intervention_dismissed', False)
    
    if mode == "morning_analysis":
        task_desc = "Mode 1: Morning Analysis (09:00 AM). Analyze metrics vs history and provide insight."
    elif mode == "evening_wind_down":
        task_desc = "Mode 2: Evening Wind-down (09:00 PM). Focus on stress levels and wind-down tips."
    else:
        task_desc = "Standard Chat Mode. Provide warm, insightful analysis."

    if is_group_msg:
        prompt = f"""
        Role: מנחה קבוצתי חכם ורגיש בתוך קבוצת וואטסאפ של פוסט-טראומה.
        Task: Analyze the group message: "{text}"
        Instructions:
        1. If the message is intense, triggering, or shows extreme distress, intervene gently.
        2. Remind the group to breathe or take a moment of silence if needed.
        3. Keep the space safe and supportive.
        4. NEVER name specific users or their personal medical data in the group.
        5. Hebrew only, empathetic and calm tone. 
        JSON Output Format: {{ "reply": "YOUR_MESSAGE_HERE" }}
        """
    else:
        prompt = f"""
        Role: אסיסטנט חכם, אנושי ורגיש בשם Deep-Rest Guard.
    User Gender: {data.get('gender')} (IMPORTANT: If female, use feminine Hebrew. If male, use masculine Hebrew).
    
    DATA FOR ANALYSIS (Only if relevant):
    - Today: HRV {data.get('hrv', 'N/A')}, RHR {data.get('resting_hr', 'N/A')}, Sleep {data.get('sleep', 'N/A')}h.
    - Survey Trends (Mood/Energy/Weather 1-5): {data.get('survey_context')}
    - Last Activity: {act_info}
    - History: {history_str}
    
    Instructions for Audio/Voice:
    - If the user sent a voice note, LISTEN carefully to their tone, pitch, and speed.
    - ANALYZE their emotional state from their voice (e.g., stressed, tired, calm, anxious).
    - REFLECT what you hear in the beginning of your response (e.g., "אני שומע בקול שלך שאת/ה...")
    - If the user has NOT sent a voice note in this session, you can warmly invite them to do so to share how they feel, mentioning it's private and helpful for releasing tension.
    
    General Instructions:
    1. PRIORITY - ACTION KEYWORDS: 
       - If message is "נשימה": Give clear, step-by-step 4-7-8 breathing instructions.
       - If message is "קרקוע": Lead a 5-4-3-2-1 grounding exercise.
       - If message is "אימון": Pick the BEST workout and give step-by-step instructions.
    
    2. STANDARD ANALYSIS:
       - Address the user by name: "היי {data.get('user_name', 'חבר')} 🤍".
       - Compare today's metrics to history. Be insightful and empathetic.
       - Give 1-2 practical tips for improvement.
       - IMPORTANT: DO NOT include a text menu. Just the analysis and tips.
    
    3. TONE: Warm, helpful, and human. 4-6 sentences. 
       - USE EMOJIS naturally (e.g., 🤍, ✨, 🧘, ⚓).
       - Emphasize privacy: "מה שנאמר כאן נשאר רק בינינו" (What is said here stays only between us).
    
    Context: {task_desc}
    Workout Protocol: {workout_protocol}
    
    User Message: "{text if text else '[Voice Note]'}"
    JSON Output Format: {{ "reply": "YOUR_MESSAGE_HERE" }}
    """
    
    contents = []
    if audio_bytes:
        contents.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"))
    
    contents.append(prompt)

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
    
    # Handle Scheduled Tasks (Morning/Evening/Research)
    task = request.args.get("task")
    if task:
        users = db.collection("users").get()
        for user_doc in users:
            u_id = user_doc.id
            u_data = user_doc.to_dict()
            name = u_data.get("name", "חבר")
            
            if task == "morning":
                g = u_data.get("gender", "male")
                m_txt = f"היי {name} 🤍 בוקר טוב ✨\nבוא/י נתחיל את היום יחד. 🌿\nבצע/י סנכרון קצר עם השעון וכתוב/כתבי לי 'בוצע' כשסיימת. 🧘"
                if g == "female":
                    m_txt = f"היי {name} 🤍 בוקר טוב ✨\nבואי נתחיל את היום יחד. 🌿\nבצעי סנכרון קצר עם השעון וכתבי לי 'בוצע' כשסיימת. 🧘"
                send_wa(u_id, m_txt)
                send_wa_poll(u_id, PCL5_QUESTIONS[0], PCL5_OPTIONS)
            
            elif task == "evening":
                g = u_data.get("gender", "male")
                e_txt = f"ערב טוב {name} 🌙\nזה הזמן שלנו להתחיל להוריד הילוך לקראת השינה. ✨"
                if g == "female":
                    e_txt = f"ערב טוב {name} 🌙\nזה הזמן שלנו להתחיל להוריד הילוך לקראת השינה. ✨" # Neutral enough
                send_wa(u_id, e_txt)
                send_wa_poll(u_id, PCL5_QUESTIONS[0], PCL5_OPTIONS)
            
            elif task == "research_poll":
                curr_idx = u_data.get("pcl5_index", 0)
                if curr_idx < len(PCL5_QUESTIONS):
                    q = PCL5_QUESTIONS[curr_idx]
                    intro = "היי {name}, הגיע זמן רגע הכנות שלנו. ✨\nנשמח שתענה/י על 4 שאלות קצרות כדי שנוכל לעקוב אחר השיפור שלך:" if curr_idx == 0 else ""
                    if intro: send_wa(u_id, intro.format(name=name))
                    send_wa_poll(u_id, q, PCL5_OPTIONS)
            
            elif task == "weekly_report":
                report = generate_weekly_report(u_id)
                if report:
                    send_wa(u_id, report)
            
            elif task == "group_pulse":
                # Triggered via ?task=group_pulse&group_id=...
                g_id = request.args.get("group_id")
                if g_id:
                    pulse_msg = get_group_pulse(g_id)
                    if pulse_msg: send_wa(g_id, pulse_msg)
            
            elif task == "group_regulation":
                g_id = request.args.get("group_id")
                if g_id:
                    reg_msg = "🧘 *זמן ויסות קבוצתי* ⚓\n\nאני מזמין את כולכם לעצור לרגע. נסו לבצע 4 מחזורי נשימה של 4-7-8 יחד עכשיו. מי שסיים שיסמן ב-✅."
                    send_wa(g_id, reg_msg)
        
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
                        <select name="gender" style="width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; background: white;" required>
                            <option value="" disabled selected>מין</option>
                            <option value="male">זכר</option>
                            <option value="female">נקבה</option>
                        </select>
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
            gender = request.form.get("gender")
            emergency_name = request.form.get("emergency_name")
            emergency_phone = request.form.get("emergency_phone")
            
            if phone and api_key and athlete_id:
                set_user_credentials(phone, api_key, athlete_id, user_name, emergency_name, emergency_phone, gender)
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
            text = ""
            
            # Fetch user doc early to avoid variable errors
            user_doc = get_user_doc(sender)
            
            # Extract text or list selection or poll response
            if msg_type == "text":
                text = msg.get("text", {}).get("body", "").strip()
            elif msg_type == "interactive":
                inter_type = msg.get("interactive", {}).get("type")
                if inter_type == "list_reply":
                    selection_id = msg["interactive"]["list_reply"]["id"]
                    # Map selection to keywords to reuse existing logic
                    if selection_id == "action_breath": 
                        text = "נשימה"
                        log_community_action(sender, "breath")
                    elif selection_id == "action_ground": 
                        text = "קרקוע"
                        log_community_action(sender, "ground")
                    elif selection_id == "action_workout": 
                        text = "אימון"
                        log_community_action(sender, "workout")
                    elif selection_id == "action_community":
                        send_wa(sender, "ברוך הבא למרכז הקהילתי של השבט. ✨", interactive_list=get_community_menu())
                        return "OK", 200
                    elif selection_id == "comm_stats":
                        u_name = user_doc.get("name", "חבר")
                        send_wa(sender, get_community_message(u_name))
                        return "OK", 200
                    elif selection_id == "comm_join_group":
                        link = "https://chat.whatsapp.com/KTYfxOQGtV9ATDroVrs5gT"
                        send_wa(sender, f"שמחים שאת/ה מצטרף/ת אלינו! 🤍\nהנה הקישור לקבוצה שלנו:\n{link}")
                        return "OK", 200
                    elif selection_id == "comm_find_partner":
                        # Opt-in logic
                        db.collection("users").document(_clean_id(sender)).set({"partner_opt_in": True}, merge=True)
                        partner = find_community_partner(sender)
                        if partner:
                            p_doc, p_id = partner
                            p_name = p_doc.get("name", "חבר מהקהילה")
                            send_wa(sender, f"מצאתי חבר/ה מהשבט שזמין/ה לחיבור! 🤝\nהשם: *{p_name}*\nאפשר לכתוב לו/לה כאן: https://wa.me/{p_id}\n\n(גם הפרופיל שלך הפך לזמין כרגע לחיפוש)")
                        else:
                            send_wa(sender, "כרגע אין חברים פנויים נוספים, אבל הפכתי את הפרופיל שלך לזמין לחיבור. ברגע שמישהו יחפש שותף, הוא יוכל למצוא אותך! ✨")
                        return "OK", 200
                    elif selection_id == "comm_opt_out":
                        db.collection("users").document(_clean_id(sender)).set({"partner_opt_in": False}, merge=True)
                        send_wa(sender, "הפרופיל שלך הוסר מרשימת החיפוש. תמיד אפשר לחזור ולהצטרף שוב! 🌿")
                        return "OK", 200
                    elif selection_id == "action_fine": text = "בסדר"
                    elif selection_id.startswith("graph_"):
                        days = int(selection_id.split("_")[1])
                        u_name = user_doc.get("name", "חבר")
                        send_wa(sender, f"מייצר עבורך גרף של {days} הימים האחרונים... ✨")
                        graph_bytes = generate_progress_graph(sender, days=days)
                        if graph_bytes:
                            media_id = upload_wa_media(graph_bytes, "progress.png", "image/png")
                            if media_id:
                                # 2. Second message (The Image with Caption)
                                caption = f"📊 *דוח התקדמות עבור {u_name}* 📈\n\nבגרף ניתן לראות את הקשר בין:\n🟢 התאוששות (HRV)\n🔵 איכות מנוחה (שינה)\n🟣 דיווח עצמי (אנרגיה)\n🔴 פעילות (עומס אימונים)\n\nהגרף עוזר לך להבין איך הגוף שלך מגיב למאמץ ולמנוחה. ✨"
                                send_wa_image(sender, media_id, caption)
                            else:
                                send_wa(sender, "מצטער, הייתה שגיאה טכנית בהכנת התמונה. נסה שוב בעוד כמה דקות. 😔")
                        else:
                            send_wa(sender, f"היי {u_name} 🤍, נראה שעדיין אין לי מספיק נתונים מהשעון כדי לצייר גרף לטווח שבחרת. אני צריך לפחות 3 ימים של מדידות רצופות כדי להראות לך מגמת שיפור אמיתית. ✨📈")
                        return "OK", 200
                    elif selection_id == "help_nefesh":
                        send_wa(sender, "⚓ *מוקד נפש אחת* (אגף השיקום - משרד הביטחון)\nחיוג מקוצר: *8944\n[לחץ כאן לחיוג](tel:*8944)")
                        return "OK", 200
                    elif selection_id == "help_natal":
                        send_wa(sender, "❤️ *נט\"ל* (נפגעי טראומה על רקע לאומי)\nחיוג ישיר: 1-800-363-363\n[לחץ כאן לחיוג](tel:1800363363)")
                        return "OK", 200
                    elif selection_id == "help_eran":
                        send_wa(sender, "👂 *ער\"ן* (עזרה ראשונה נפשית)\nחיוג מקוצר: 1201\n[לחץ כאן לחיוג](tel:1201)")
                        return "OK", 200
                    elif selection_id == "help_sahar":
                        send_wa(sender, "💬 *סה\"ר* (סיוע והקשבה ברשת)\nוואטסאפ זמין: 055-957-1399\n[לחץ כאן לשליחת הודעה](https://wa.me/972559571399)")
                        return "OK", 200
                    elif selection_id == "action_help_contact":
                        u_name = user_doc.get("name", "חבר")
                        e_name = user_doc.get("emergency_name")
                        e_phone = user_doc.get("emergency_phone")
                        if e_phone:
                            # 1. Activate Emergency Mode for 15 minutes
                            doc_id = _clean_id(sender)
                            expiry = (datetime.datetime.now() + datetime.timedelta(minutes=15)).isoformat()
                            db.collection("users").document(doc_id).set({"emergency_mode_expiry": expiry}, merge=True)
                            
                            # 2. Send Alert
                            sender_clean = sender.replace("+", "")
                            alert_msg = f"⚓ הודעה מ-Deep-Rest Guard: {u_name} ביקש/ה לעדכן אותך שהוא/היא נמצא/ת ברגע של עומס רגשי וזקוק/ה לתמיכה. כדאי ליצור קשר בהקדם. 🤍\n\nליצירת קשר מהיר:\nhttps://wa.me/{sender_clean}"
                            send_wa(e_phone, alert_msg)
                            send_wa(sender, f"שלחתי הודעה דחופה ל{e_name}. ✨\n\nב-15 הדקות הקרובות, כל תמונה, מיקום או הקלטה שתשלח/י לי כאן יועברו אליו/אליה מיד כדי שיוכלו לעזור. 📍🖼️🎤")
                        else:
                            send_wa(sender, "לא הגדרת מספר טלפון לאיש קשר לחירום. 🌿")
                        return "OK", 200
                    elif selection_id.startswith("poll_ans_"):
                        option_id = selection_id.split("_")[-1]
                        
                        # Store response in user doc and in daily history for graphing
                        doc_id = _clean_id(sender)
                        user_doc = get_user_doc(sender)
                        curr_idx = user_doc.get("pcl5_index", 0)
                        today_id = datetime.date.today().isoformat()
                        
                        # 1. Update database
                        new_idx = curr_idx + 1
                        db.collection("users").document(doc_id).set({
                            "pcl5_responses": {str(curr_idx): option_id},
                            "pcl5_index": new_idx
                        }, merge=True)
                        
                        # 2. Store in daily history for the graph
                        hist_ref = db.collection("users").document(doc_id).collection("wellness_history").document(today_id)
                        hist_ref.set({f"survey_{curr_idx}": int(option_id)}, merge=True)
                        
                        # 3. Check if survey continues or ends
                        if new_idx < len(PCL5_QUESTIONS):
                            next_q = PCL5_QUESTIONS[new_idx]
                            send_wa_poll(sender, next_q, PCL5_OPTIONS)
                        else:
                            # End of survey
                            u_name = user_doc.get("name", "חבר")
                            send_wa(sender, f"תודה על השיתוף, {u_name}! ✨\nמייצר עבורך את דוח ההתקדמות השבועי המעודכן... 📊")
                            
                            # Fetch current metrics for the caption
                            try:
                                data = fetch_intervals_data(sender)
                                hrv = data.get('hrv', 'N/A')
                                sleep = data.get('sleep', 'N/A')
                                energy = option_id # The last answer is energy/weather
                                
                                # Generate and send graph
                                graph_bytes = generate_progress_graph(sender, days=7)
                                if graph_bytes:
                                    media_id = upload_wa_media(graph_bytes, "progress.png", "image/png")
                                    if media_id:
                                        caption = f"📊 *דוח התקדמות עבור {u_name}* 📈\n\n"
                                        caption += f"🟢 התאוששות (HRV): {hrv} ms\n"
                                        caption += f"🔵 איכות מנוחה (שינה): {sleep} שעות\n"
                                        caption += f"🟣 דיווח עצמי (אנרגיה): {energy}/5\n\n"
                                        caption += "הגרף מציג את המגמה שלך ב-7 הימים האחרונים. ✨"
                                        send_wa_image(sender, media_id, caption)
                            except:
                                # Fallback if intervals data fails
                                graph_bytes = generate_progress_graph(sender, days=7)
                                if graph_bytes:
                                    media_id = upload_wa_media(graph_bytes, "progress.png", "image/png")
                                    if media_id:
                                        send_wa_image(sender, media_id, f"📊 דוח התקדמות שבועי עבור {u_name} ✨")
                        return "OK", 200
            elif msg_type == "location":
                loc_data = msg.get("location", {})
                lat = loc_data.get("latitude")
                lon = loc_data.get("longitude")
                
                e_phone = user_doc.get("emergency_phone")
                e_name = user_doc.get("emergency_name", "איש הקשר")
                u_name = user_doc.get("name", "חבר")
                
                if e_phone:
                    # Notify emergency contact with location
                    send_wa(e_phone, f"📍 *עדכון מיקום דחוף* מ-{u_name}:")
                    send_wa_location(e_phone, lat, lon, name=f"המיקום של {u_name}")
                    send_wa(sender, f"המיקום שלך נשלח ל{e_name}. אנחנו איתך. ⚓")
                else:
                    send_wa(sender, "שלחת מיקום, אבל לא הגדרת איש קשר לחירום שאוכל להעביר לו אותו. 🌿")
                return "OK", 200
            elif msg_type == "location":
                loc_data = msg.get("location", {})
                lat = loc_data.get("latitude")
                lon = loc_data.get("longitude")
                
                e_phone = user_doc.get("emergency_phone")
                e_name = user_doc.get("emergency_name", "איש הקשר")
                u_name = user_doc.get("name", "חבר")
                
                if e_phone:
                    # Notify emergency contact with location
                    send_wa(e_phone, f"📍 *עדכון מיקום דחוף* מ-{u_name}:")
                    send_wa_location(e_phone, lat, lon, name=f"המיקום של {u_name}")
                    send_wa(sender, f"המיקום שלך נשלח ל{e_name}. אנחנו איתך. ⚓")
                else:
                    send_wa(sender, "שלחת מיקום, אבל לא הגדרת איש קשר לחירום שאוכל להעביר לו אותו. 🌿")
                return "OK", 200
            elif msg_type == "image":
                image_id = msg.get("image", {}).get("id")
                e_phone = user_doc.get("emergency_phone")
                e_name = user_doc.get("emergency_name", "איש הקשר")
                u_name = user_doc.get("name", "חבר")
                
                # Check if Emergency Mode is active
                emergency_expiry = user_doc.get("emergency_mode_expiry")
                is_emergency = emergency_expiry and datetime.datetime.fromisoformat(emergency_expiry) > datetime.datetime.now()
                
                if is_emergency and e_phone and image_id:
                    send_wa(e_phone, f"🖼️ *תמונה דחופה* מ-{u_name}:")
                    send_wa_image(e_phone, image_id)
                    send_wa(sender, f"התמונה נשלחה ל{e_name}. ⚓")
                else:
                    send_wa(sender, "קיבלתי את התמונה, תודה. ✨")
                return "OK", 200
            elif msg_type == "audio" or msg_type == "voice":
                media_id = msg.get("audio", {}).get("id") or msg.get("voice", {}).get("id")
                e_phone = user_doc.get("emergency_phone")
                e_name = user_doc.get("emergency_name", "איש הקשר")
                u_name = user_doc.get("name", "חבר")
                
                # Check if Emergency Mode is active
                emergency_expiry = user_doc.get("emergency_mode_expiry")
                is_emergency = emergency_expiry and datetime.datetime.fromisoformat(emergency_expiry) > datetime.datetime.now()
                
                # 1. Forward to emergency contact ONLY if in emergency mode
                if is_emergency and e_phone and media_id:
                    send_wa(e_phone, f"🎤 *הקלטה דחופה* מ-{u_name}:")
                    send_wa_audio(e_phone, media_id)
                    send_wa(sender, f"ההקלטה נשלחה ל{e_name}. ⚓")
                
                # 2. Process for AI (always do this for personal support)
                if media_id:
                    print(f"Downloading voice note {media_id} for AI analysis...")
                    audio_bytes = download_wa_media(media_id)
                    if audio_bytes:
                        text = "[המשתמש שלח הודעה קולית. אנא הקשב לתוכן שלה ותענה בהתאם]"
                    else:
                        text = "[הודעה קולית שלא הצלחתי להוריד]"
            elif msg_type == "poll":
                # Fallback for native polls if they ever start working
                poll_data = msg.get("poll", {})
                selected = poll_data.get("selected_options", [{}])[0]
                option_id = selected.get("id")
                
                # Store PCL-5 response
                user_doc = get_user_doc(sender)
                curr_idx = user_doc.get("pcl5_index", 0)
                
                # Update database
                db.collection("users").document(_clean_id(sender)).set({
                    "pcl5_responses": {str(curr_idx): option_id},
                    "pcl5_index": (curr_idx + 1) % len(PCL5_QUESTIONS)
                }, merge=True)
                
                # For our 4-question research, let's send them one by one
                if (curr_idx + 1) < len(PCL5_QUESTIONS):
                    next_q = PCL5_QUESTIONS[curr_idx + 1]
                    send_wa_poll(sender, next_q, PCL5_OPTIONS)
                else:
                    # End of survey - invite to record voice note
                    u_name = user_doc.get("name", "חבר")
                    end_msg = f"תודה על השיתוף, {u_name}. ✨\n\nלפני שממשיכים, אשמח לשמוע אותך. 🎤\nתשלח/י לי הודעה קולית קצרה ותספר/י לי עוד קצת על איך את/ה מרגיש/ה? \nשיתוף בקול עוזר לשחרר מתח ולהרגיע את המערכת. ⚓\n\n(זה נשאר רק בינינו 🔒)"
                    send_wa(sender, end_msg)
                
                return "OK", 200

            audio_bytes = None

            print(f"MESSAGE from {sender} (type: {msg_type}): '{text}'")

            user_doc = get_user_doc(sender)

            # --- Handle Voice Notes ---
            if msg_type == "audio" or msg_type == "voice":
                media_id = msg.get("audio", {}).get("id") or msg.get("voice", {}).get("id")
                if media_id:
                    print(f"Downloading voice note {media_id}...")
                    audio_bytes = download_wa_media(media_id)
                    if audio_bytes:
                        print(f"Voice note downloaded successfully ({len(audio_bytes)} bytes)")
                        text = "[המשתמש שלח הודעה קולית. אנא הקשב לתוכן שלה ותענה בהתאם]"
                    else:
                        print("Failed to download voice note.")
                        text = "[הודעה קולית שלא הצלחתי להוריד]"

            # --- Intervention Protocol: Emergency Contact ---
            if "עזרה" in text or "עזרי" in text:
                u_name = user_doc.get("name", "חבר")
                
                # Send the interactive help menu only
                welcome_help = f"היי {u_name}, אני כאן איתך. ✨\nבחר/י את הכלי שיכול לעזור לך כרגע לווסת את המערכת או ליצור קשר עם מוקדי סיוע:"
                send_wa(sender, welcome_help, interactive_list=get_emergency_list(emergency_name=user_doc.get("emergency_name")))
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

            if "סקר" in text:
                # Manual trigger for testing
                doc_id = _clean_id(sender)
                db.collection("users").document(doc_id).set({"pcl5_index": 0}, merge=True)
                # Send the first question directly
                send_wa_poll(sender, PCL5_QUESTIONS[0], PCL5_OPTIONS)
                return "OK", 200

            if "גרף" in text:
                send_wa(sender, "איזה טווח זמן תרצה/י לראות בגרף?", interactive_list=get_graph_menu())
                return "OK", 200

            if len(text) < 10 and text.startswith("i") and any(char.isdigit() for char in text):
                send_wa(sender, "נראה ששלחת לי Athlete ID. כדי להשלים את החיבור, שלח לי את ה-API Key שלך בפורמט הבא:\nהגדר " + text + " [API_KEY]")
                return "OK", 200

            try:
                intervals_data = fetch_intervals_data(sender)
                
                # Check if admin notification is needed
                notify_admin_if_needed(sender, intervals_data)
                
                reply = get_ai_reply(text, intervals_data, audio_bytes=audio_bytes, is_group_msg=is_group(sender))
                
                if is_group(sender):
                    # In group, don't show the personal help list unless specifically requested
                    send_wa(sender, reply)
                else:
                    # Use the interactive list for EVERY AI reply as requested
                    e_name = user_doc.get("emergency_name")
                    send_wa(sender, reply, interactive_list=get_emergency_list(body_text=reply, emergency_name=e_name))
            except Exception as e:
                if "User not connected" in str(e):
                    send_wa(sender, f"היי {user_doc.get('name', 'חבר')}, אני עדיין לא מכיר את המדדים שלך. ✨ שלח 'חבר' כדי שנתחבר יחד.")
                else:
                    print(f"ERROR: {e}")
                    dummy_data = {"user_name": user_doc.get("name", "חבר"), "emergency_name": user_doc.get("emergency_name")}
                    reply = get_ai_reply(text, dummy_data, audio_bytes=audio_bytes)
                    e_name = user_doc.get("emergency_name")
                    send_wa(sender, reply, interactive_list=get_emergency_list(body_text=reply, emergency_name=e_name))

        return "OK", 200
    except Exception as e:
        print(f"GLOBAL ERROR: {e}")
        return "OK", 200
