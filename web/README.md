# אתר שליטה ל־Sportrauma

## מה זה
אתר פרטי למשתמש שמתחבר ל־Firestore ולבוט וואטסאפ, ומאפשר לבצע פעולות על הבוט.

## דרישות
- פרויקט Firebase פעיל עם Auth (Phone), Firestore.
- הערכים של `firebaseConfig`.
- כתובת ה־Cloud Function (bot).

## איך להפעיל
1. ערוך את `web/config.js` והכנס:
   - `apiKey`, `authDomain`, `projectId`, `appId`
   - `botApiBase` (ברירת מחדל כבר מוגדרת)
2. העלה את התיקייה `web/` לכל שירות Hosting (Firebase Hosting / Netlify / Vercel).

## אבטחה
כל פעולה באתר נשלחת ל־`/site_action` עם Firebase ID token.
השרת מאמת שהטלפון תואם למשתמש לפני ביצוע פעולה.
