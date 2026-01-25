#!/bin/bash
set -euo pipefail

echo "🚀 Deploying garmin-bot-v2..."

# Optional: load local env file (do NOT commit real secrets)
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

: "${GOOGLE_OAUTH_CLIENT_ID:?Missing GOOGLE_OAUTH_CLIENT_ID}"
: "${GOOGLE_OAUTH_CLIENT_SECRET:?Missing GOOGLE_OAUTH_CLIENT_SECRET}"
: "${GEMINI_API_KEY:?Missing GEMINI_API_KEY}"
: "${WA_TOKEN:?Missing WA_TOKEN}"
: "${PHONE_NUMBER_ID:?Missing PHONE_NUMBER_ID}"
: "${VERIFY_TOKEN:?Missing VERIFY_TOKEN}"

GOOGLE_OAUTH_REDIRECT_URI="${GOOGLE_OAUTH_REDIRECT_URI:-https://us-central1-sportruma.cloudfunctions.net/garmin-bot-v2/oauth2callback}"

gcloud functions deploy garmin-bot-v2 \
  --gen2 \
  --region=us-central1 \
  --runtime=python312 \
  --source=. \
  --entry-point=whatsapp_bot \
  --trigger-http \
  --allow-unauthenticated \
  --memory=512Mi \
  --set-env-vars GOOGLE_OAUTH_CLIENT_ID="$GOOGLE_OAUTH_CLIENT_ID",GOOGLE_OAUTH_CLIENT_SECRET="$GOOGLE_OAUTH_CLIENT_SECRET",GOOGLE_OAUTH_REDIRECT_URI="$GOOGLE_OAUTH_REDIRECT_URI",GEMINI_API_KEY="$GEMINI_API_KEY",WA_TOKEN="$WA_TOKEN",PHONE_NUMBER_ID="$PHONE_NUMBER_ID",VERIFY_TOKEN="$VERIFY_TOKEN"

echo "✅ Done!"
