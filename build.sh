#!/usr/bin/env bash

echo "✅ Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Installing Playwright browser dependencies..."
python -m playwright install chromium

echo "✅ Build finished. Chromium should be ready."