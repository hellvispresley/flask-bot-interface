from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import random
import sys
import requests
import re
from playwright.sync_api import sync_playwright

app = Flask(__name__)
client = OpenAI()

# Dummy tweets for placeholder behavior
sample_tweets = [
    "Just had the best coffee ever!",
    "Can't believe how sunny it is today.",
    "Reading a fascinating book on AI.",
    "Workout completed. Feeling great!",
    "Cooking a new recipe tonight."
]

# ---- Primary routes ---- #

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/generate", methods=["POST"])
def generate_tweet():
    # TODO: Replace with GPT-based generation later
    tweet = random.choice(sample_tweets)
    return jsonify({"tweet": tweet})

@app.route("/api/engage", methods=["POST"])
def engage_tweet():
    data = request.get_json()
    tweet_url = data.get("url")
    persona = data.get("persona")  # <== include this if you want GPT persona behavior

    tweet_text = get_tweet_text_from_url(tweet_url)
    if not tweet_text:
        return jsonify({"tweet": "❌ Could not extract tweet content from the URL."})

    response = f"{persona or 'Someone'} engaging with: {tweet_text[:200]}..."
    return jsonify({"tweet": response})
# ---- Tweet extraction with fallback ---- #

def get_tweet_text_from_url(tweet_url):
    def _extract_with_playwright():
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--disable-gpu"
                    ]
                )
                page = browser.new_page()
                page.goto(tweet_url, timeout=20000)
                page.wait_for_selector("article div[lang]", timeout=20000)
                full_text = page.locator("article div[lang]").inner_text()
                print("🔍 Chromium scrape success:\n", full_text[:1000])
                sys.stdout.flush()
                browser.close()
                return full_text
        except Exception as e:
            print("❌ Chromium scrape failed:", e)
            sys.stdout.flush()
            return None

    def _extract_with_oembed():
        try:
            res = requests.get(
                "https://publish.twitter.com/oembed",
                params={"url": tweet_url},
                timeout=10
            )
            if res.status_code == 200:
                html = res.json().get("html", "")
                matches = re.findall(r"<p.*?>(.*?)</p>", html)
                text = re.sub(r"<.*?>", "", " ".join(matches)).strip()
                print("🟡 Fallback oEmbed success:\n", text[:1000])
                sys.stdout.flush()
                return text if text else None
        except Exception as e:
            print("❌ oEmbed fallback failed:", e)
            sys.stdout.flush()
            return None

    return _extract_with_playwright() or _extract_with_oembed()

if __name__ == "__main__":
    app.run(debug=True)