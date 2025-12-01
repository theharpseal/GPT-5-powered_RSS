import os
import json
import requests
import feedparser
from openai import OpenAI

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not WEBHOOK_URL or not OPENAI_API_KEY:
    raise RuntimeError("Missing DISCORD_WEBHOOK_URL or OPENAI_API_KEY env vars")

client = OpenAI(api_key=OPENAI_API_KEY)

FEEDS = [
    "https://arxiv.org/rss/cs.RO",       # Robotics
    "https://arxiv.org/rss/eess.SP",     # Example second feed
]

STATE_FILE = "seen.json"


def load_seen():
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)


def summarize(text: str) -> str:
    text = text[:6000]

    prompt = (
        "You are summarizing new research papers for a busy engineering student "
        "interested in robotics, semiconductors, and AI.\n\n"
        "Given the abstract/description below, respond with:\n"
        "- Exactly 3 bullet points.\n"
        "- Max ~20 words per bullet.\n"
        "- Focus on: (1) what the work does, (2) what’s novel, (3) why it matters / who cares.\n\n"
        f"ABSTRACT / DESCRIPTION:\n{text}"
    )

    response = client.chat.completions.create(
        model="gpt-5.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=220,
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()


def post_to_discord(title: str, link: str, summary: str):
    content = f"**New paper:** {title}\n{link}\n\n**AI summary (GPT-5.1 mini):**\n{summary}"
    payload = {"content": content}
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()


def main():
    seen = load_seen()

    for feed_url in FEEDS:
        parsed = feedparser.parse(feed_url)

        for entry in parsed.entries:
            uid = entry.get("id") or entry.get("link")
            if not uid:
                continue

            if uid in seen:
                continue

            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            description = getattr(entry, "summary", "") or title

            try:
                summary = summarize(description)
                post_to_discord(title, link, summary)
                print(f"Posted: {title}")
            except Exception as e:
                print(f"Error processing '{title}': {e}")

            seen.add(uid)

    save_seen(seen)


if __name__ == "__main__":
    main()

