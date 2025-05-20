#!/usr/bin/env bash

echo "✅ Installing Python dependencies..."
pip install -r requirements.txt

echo "✅ Installing Playwright browser (verbose)..."
DEBUG=pw:install python -m playwright install chromium || {
  echo "❌ Chromium install failed!"
  exit 1
}

echo "✅ Build finished. Chromium installed successfully."