#!/bin/bash
echo "🚀 Deploying garmin-bot-v2..."
gcloud functions deploy garmin-bot-v2 --gen2 --region=us-central1 --runtime=python312 --source=. --entry-point=whatsapp_bot --trigger-http --allow-unauthenticated --memory=512Mi
echo "✅ Done!"
