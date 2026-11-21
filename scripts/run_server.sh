#!/bin/bash
set -e

echo "Starting Toolpika backend..."
uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --workers 4
