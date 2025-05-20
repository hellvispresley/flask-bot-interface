import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from openai import AsyncOpenAI
from datetime import datetime
from pathlib import Path

# Load credentials
load_dotenv(dotenv_path=".env")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TWITTER_USERNAME or not TWITTER_PASSWORD or not OPENAI_API_KEY:
    raise ValueError("Missing credentials! Check your .env file.")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Save the thread to a file
def save_thread_to_file(thread_text, author="RighteousRyght", source_user="Unknown"):
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H-%M-%S")

    folder = Path(f"output/{date_str}")
    folder.mkdir(parents=True, exist_ok=True)

    filename = folder / f"{author}_{time_str}.txt"

    header = f"""\n🔥 {author} Thread 🔥\n🗓️ {date_str}\n🎯 Based on tweet by: {source_user}\n\n{thread_text}"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(header)

    print(f"\n📁 Saved thread to {filename}")

# Twitter login
async def login_to_twitter(page):
    await page.goto("https://twitter.com/login", timeout=60000)
    await page.wait_for_selector('input[autocomplete="username"]', timeout=15000)
    await page.fill('input[autocomplete="username"]', TWITTER_USERNAME)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(2000)

    await page.wait_for_selector('input[autocomplete="current-password"]', timeout=15000)
    await page.fill('input[autocomplete="current-password"]', TWITTER_PASSWORD)
    await page.keyboard.press("Enter")
    await page.wait_for_selector('article', timeout=20000)
    print("Login successful")

# YouTube search and extract first video URL
async def fetch_youtube_url(playwright, topic):
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.goto(f"https://www.youtube.com/results?search_query={topic}")
    await page.wait_for_selector("ytd-video-renderer", timeout=10000)

    video = await page.locator("ytd-video-renderer a#thumbnail").first.get_attribute("href")
    await browser.close()

    if video:
        return f"https://www.youtube.com{video}"
    else:
        return ""

# Generate GPT response
async def generate_conservative_response(tweet_text, youtube_url):
    system_prompt = (
        "You are RighteousRyght, a hard-right political commentator who delivers fiery, sarcastic, and conspiracy-tinged threads. "
        "You mock mainstream narratives, expose 'hidden agendas,' and speak with unwavering confidence. "
        "Your threads start with a powerful hook and then break into 3 escalating sub-posts. End strong and memorable."
    )

    user_prompt = f"""
Write a conservative Twitter thread responding to this tweet:
"{tweet_text}"

Format:
Post 1 (main tweet):
Post 2:
Post 3:
Post 4:
"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.9,
            max_tokens=600
        )

        thread = response.choices[0].message.content.strip()
        lines = thread.splitlines()

        # Inject YouTube URL into Post 1
        for i, line in enumerate(lines):
            if line.strip().lower().startswith("post 1") and i + 1 < len(lines):
                lines[i + 1] += f" 🎥 {youtube_url}"
                break

        return "\n".join(lines)

    except Exception as e:
        print(f"❌ GPT generation failed: {e}")
        return "ERROR: GPT failed to generate content."

# Scrape tweets from trending topic and generate thread
async def scrape_trending_tweets():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        await login_to_twitter(page)

        print("Clicking Explore...")
        await page.get_by_test_id("AppTabBar_Explore_Link").click()
        await page.wait_for_timeout(3000)

        print("Clicking Trending tab...")
        trending_tab = page.get_by_role("tab", name="Trending")
        await trending_tab.wait_for(timeout=10000)
        if await trending_tab.get_attribute("aria-selected") != "true":
            await trending_tab.click()
            await page.wait_for_timeout(3000)

        print("Clicking first trending topic...")
        first_topic = page.locator("div[data-testid='trend']").first
        await first_topic.wait_for(timeout=10000)
        topic_text = await first_topic.inner_text()
        await first_topic.click()
        await page.wait_for_timeout(3000)

        print("Scraping tweets...")
        await page.wait_for_selector("article", timeout=30000)
        tweets = await page.query_selector_all("article")

        trending_posts = []
        for tweet in tweets[:10]:
            try:
                content = await tweet.inner_text()
                user = await tweet.query_selector('div[dir="ltr"] span')
                username = await user.inner_text() if user else "Unknown"
                trending_posts.append({"user": username, "content": content})
            except:
                continue

        await browser.close()

        if trending_posts:
            print("\n🔵 Scraping YouTube for:", topic_text)
            youtube_url = await fetch_youtube_url(p, topic_text.splitlines()[0])
            response = await generate_conservative_response(trending_posts[0]['content'], youtube_url)
            print("\n--- RighteousRyght Thread ---")
            print(response)
            save_thread_to_file(response, author="RighteousRyght", source_user=trending_posts[0]['user'])

# Entry point
if __name__ == "__main__":
    asyncio.run(scrape_trending_tweets())