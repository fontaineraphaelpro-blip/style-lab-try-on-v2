#!/bin/bash

# Script de démarrage pour Render
# Démarre le serveur FastAPI avec Uvicorn

echo "🚀 Starting VTON AI Backend..."
echo "📍 Port: $PORT"

# Démarrer Uvicorn
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT:-10000} \
    --workers 1 \
    --log-level info \
    --timeout-keep-alive 120
