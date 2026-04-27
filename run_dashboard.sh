#!/bin/bash

# SH-AI Heal Command Center Bootstrapper
echo "🧬 Starting Self-Healing AI Control Center (FastAPI)..."

# Ensure we're using the virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Setting up virtual environment..."
    python3 -m venv venv
fi

# Install/Update dependencies
echo "📦 Installing requirements..."
./venv/bin/pip install -r requirements.txt

# Determine Local IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")

echo "--------------------------------------------------"
echo "🚀 API & Dashboard starting on http://$LOCAL_IP:8000"
echo "📄 API Docs available at http://$LOCAL_IP:8000/docs"
echo "--------------------------------------------------"

# Start the server using uvicorn via venv
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
