from flask import Flask, render_template, request, redirect, url_for, Response
import asyncio
import os
from scrape import scrape_trending_tweets, save_thread_to_file
from openai import OpenAI
from urllib.parse import urlparse
import re
from playwright.sync_api import sync_playwright

# ✅ Environment setup (remove if no longer needed)

app = Flask(__name__)
OUTPUT_DIR = "output"
client = OpenAI()

# ✅ AUTH USERS
AUTHORIZED_USERS = {
    "hebro": "Sambo12!",
    "friend": "hispassword456"
}

def check_auth(username, password):
    return username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password

def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def require_auth(view_func):
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return view_func(*args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper

@app.route("/")
@require_auth
def index():
    return render_template("index.html")

@app.route("/generate-thread", methods=["POST"])
@require_auth
def generate_thread():
    asyncio.run(scrape_trending_tweets())
    return redirect(url_for('view_threads'))

@app.route("/engage", methods=["POST"])
@require_auth
def engage():
    tweet_url = request.form.get("tweet_url")
    persona = request.form.get("persona")
    tweet_text = get_tweet_text_from_url(tweet_url)
    if not tweet_text:
        return render_template("index.html", responses=["❌ Could not extract tweet content from the URL."])
    gpt_responses = generate_engagement_responses(tweet_text, persona)
    return render_template("index.html", responses=gpt_responses, selected_persona=persona)

@app.route("/rephrase", methods=["POST"])
@require_auth
def rephrase():
    original_reply = request.form.get("original_reply")
    persona = request.form.get("persona")
    rephrased = generate_original_tweet_thread(original_reply, persona)
    return render_template("index.html", original_thread=rephrased)

@app.route("/threads")
@require_auth
def view_threads():
    threads = []
    for foldername, _, filenames in os.walk(OUTPUT_DIR):
        for filename in filenames:
            if filename.endswith(".txt"):
                rel_path = os.path.join(foldername, filename).replace("\\", "/")
                threads.append(rel_path[len(OUTPUT_DIR)+1:])
    threads.sort(reverse=True)
    return render_template("threads.html", threads=threads)

@app.route("/thread/<path:filename>")
@require_auth
def view_thread(filename):
    full_path = os.path.join(OUTPUT_DIR, filename)
    with open(full_path, encoding="utf-8") as f:
        content = f.read()
    return render_template("thread_viewer.html", thread=content)

def get_tweet_text_from_url(tweet_url):
    def _extract():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(tweet_url, timeout=15000)
                page.wait_for_selector("article div[lang]", timeout=10000)
                tweet_content = page.locator("article div[lang]").inner_text()
                browser.close()
                return tweet_content
            except Exception as e:
                browser.close()
                print(f"Error scraping tweet: {e}")
                return None
    return _extract()

def generate_engagement_responses(tweet_text, persona):
    system_prompt = get_persona_prompt(persona) + "Your replies must be under 280 characters and punchy."
    user_prompt = f"""Write 3 different tweet replies under 280 characters each, in the voice of {persona}, responding to this tweet:\n\n"{tweet_text}"\n\nNumber each reply as 1, 2, and 3:"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.85,
            max_tokens=800
        )
        raw_output = response.choices[0].message.content.strip()
        replies = re.findall(r"(?:^|\n)[123]\.\s*(.*)", raw_output)
        cleaned = [r.strip() for r in replies if len(r.strip()) <= 280]
        return cleaned if cleaned else [raw_output]
    except Exception as e:
        return [f"❌ GPT failed to generate responses: {e}"]

def generate_original_tweet_thread(reply_text, persona):
    system_prompt = get_persona_prompt(persona) + (
        "You are now repackaging a tweet reply as an original viral thread. "
        "Write 2–3 posts max, each under 280 characters, in the same voice. Include emojis or 🔥 punchy hooks. "
        "Avoid mentioning it's a reply or referring to another tweet."
    )
    user_prompt = f"""Rewrite the following as a standalone tweet thread (2-3 posts). Keep each post under 280 characters:\n\n"{reply_text}"\n\nFormat:\nPost 1:\nPost 2:\n(Post 3 if needed)"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.85,
            max_tokens=800
        )
        output = response.choices[0].message.content.strip()
        posts = re.findall(r"Post \d+:\s*(.*)", output)
        return [p.strip() for p in posts if len(p.strip()) <= 280]
    except Exception as e:
        return [f"❌ GPT failed to rephrase: {e}"]

def get_persona_prompt(persona):
    if persona == "RighteousRyght":
        return (
            "You are RighteousRyght, a hard-right political commentator. Father, Patriot, Christian. "
            "You mock mainstream narratives, expose 'hidden agendas,' and write with sarcasm, fury, and confidence. "
            "You often tie in conspiracy theories and viral hooks. "
        )
    elif persona == "CentristStan":
        return (
            "You are CentristStan, a neutral, logical, and fact-driven responder. "
            "You avoid drama and calmly explain alternative views. "
        )
    elif persona == "LeftyLoretta":
        return (
            "You are LeftyLoretta, a progressive activist and satirist. Cat mom, Anarchist and anti-establishment. "
            "Pro-LGBTQ+ and Gender Fluid Supporter. If they don't agree with you they are probably racist nazis. "
            "You respond with wit, passion, and left-leaning social commentary. "
        )
    return ""

if __name__ == "__main__":
    app.run(debug=True)