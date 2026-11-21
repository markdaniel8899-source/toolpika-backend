#!/bin/bash
set -e

echo "Deploying Toolpika Backend..."

cd /opt/toolpika/backend
git pull origin main

pip install -r requirements.txt

python scripts/migrate.py > /tmp/toolpika-migration.sql
echo "Migration SQL written to /tmp/toolpika-migration.sql (apply in Supabase)"

APP_ENV=test pytest tests/ -v --tb=short

sudo systemctl restart toolpika-backend

echo "Deployment complete"
