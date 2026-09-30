#!/bin/bash
set -e

echo "🚀 [1/3] Pulling latest changes from Git..."
git pull origin main

if [ -f "docker-compose.yml" ] && command -v docker &> /dev/null; then
    echo "🐳 [2/3] Rebuilding & restarting Docker container..."
    docker compose up -d --build
    echo "✅ [3/3] Deployment complete! App is running."
elif systemctl is-active --quiet asykar-daytrade 2>/dev/null; then
    echo "🔄 [2/3] Updating python dependencies & restarting systemd service..."
    if [ -d ".venv" ]; then
        .venv/bin/pip install -r requirements.txt -q
    fi
    systemctl restart asykar-daytrade
    echo "✅ [3/3] Deployment complete! Service restarted."
else
    echo "ℹ️  Git pull complete. Please start or restart your service."
fi
