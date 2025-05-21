from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import random
import sys
import requests
import re
from playwright.sync_api import sync_playwright

app = Flask(__name__)
client = OpenAI()

sample_tweets = [
    "Just had the best coffee ever!",
    "Can't believe how sunny it is today.",
    "Reading a fascinating book on AI.",
    "Workout completed. Feeling great!",
    "Cooking a new recipe tonight."
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/generate", methods=["POST"])
def generate_tweet():
    tweet = random.choice(sample_tweets)
    return jsonify({"tweet": tweet})

@app.route("/api/engage", methods=["POST"])
def engage_tweet():
    data = request.get_json()
    tweet_url = data.get("url")
    persona = data.get("persona")

    tweet_text = get_tweet_text_from_url(tweet_url)
    if not tweet_text:
        return jsonify({"replies": ["❌ Could not extract tweet content from the URL."]})

    system_prompt = get_persona_prompt(persona)
    user_prompt = f"""Write 3 tweet replies (280 characters max each) in the voice of {persona}, responding to:\n\n"{tweet_text}"\n\nNumber them 1, 2, and 3."""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,
            max_tokens=800
        )
        text = response.choices[0].message.content
        replies = re.findall(r"(?:^|\n)[123]\.\s*(.*)", text)
        return jsonify({"replies": replies})
    except Exception as e:
        return jsonify({"replies": [f"❌ GPT error: {e}"]})

@app.route("/api/generate-similar", methods=["POST"])
def generate_similar():
    data = request.get_json()
    original = data.get("text", "")
    persona = data.get("persona", "RighteousRyght")

    if not original:
        return jsonify({"tweet": "❌ No seed text provided."})

    system_prompt = get_persona_prompt(persona)
    user_prompt = f"""Create a tweet inspired by the following:\n\n"{original}"\n\nIt should be original, punchy, under 280 characters, and clearly written in the voice of {persona}."""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.85,
            max_tokens=300
        )
        tweet = response.choices[0].message.content.strip()
        return jsonify({"tweet": tweet})
    except Exception as e:
        return jsonify({"tweet": f"❌ GPT error: {e}"})


@app.route("/api/trending", methods=["GET"])
def fetch_trending():
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            page = browser.new_page()
            page.goto("https://twitter.com/explore/tabs/trending", timeout=20000)
            page.wait_for_selector("article", timeout=10000)

            tweets = page.query_selector_all("article")
            results = []

            for tweet in tweets[:20]:
                try:
                    text = tweet.inner_text()
                    url_node = tweet.query_selector("a[href*='/status/']")
                    link = url_node.get_attribute("href") if url_node else None
                    if text and link:
                        results.append({
                            "text": text.split("\n")[0][:280],
                            "url": f"https://twitter.com{link}"
                        })
                except Exception as e:
                    print("⚠️ Skipping tweet due to error:", e)
                    continue

            browser.close()
            return jsonify({"tweets": results[:10]})
    except Exception as e:
        print("❌ Trending scrape failed:", e)
        return jsonify({"error": str(e)})

def get_persona_prompt(persona):
    if persona == "RighteousRyght":
        return "You are RighteousRyght, a hard-right political commentator. Write fiery, sarcastic, punchy conservative takes."
    elif persona == "LeftyLoretta":
        return "You are LeftyLoretta, a progressive activist and cat mom. Respond with witty, pro-LGBTQ+, anti-establishment humor."
    elif persona == "CentristStan":
        return "You are CentristStan, a neutral, factual explainer who avoids drama. Respond calmly and rationally."
    return "You are a generic internet user."

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
                browser.close()
                return full_text
        except Exception as e:
            print("❌ Chromium scrape failed:", e)
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
                return text if text else None
        except Exception as e:
            print("❌ oEmbed fallback failed:", e)
            return None

    return _extract_with_playwright() or _extract_with_oembed()

if __name__ == "__main__":
    app.run(debug=True)