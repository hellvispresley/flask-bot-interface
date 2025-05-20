#!/usr/bin/env bash

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
npx playwright install chromium

echo "✅ Build complete"