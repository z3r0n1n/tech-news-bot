import os
import json
import feedparser
import asyncio
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime
import re

# --- CONFIGURAZIONE ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TOPIC_ID = int(os.environ.get("TOPIC_ID"))

FEED_URLS = [
    "https://www.theverge.com/rss/index.xml",
    "https://techcrunch.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://www.engadget.com/rss.xml",
    "https://www.wired.com/feed/rss",
]

CHECK_INTERVAL = 1800  # 30 minuti
SEEN_FILE = "seen_entries.json"
SIMILARITY_THRESHOLD = 0.6  # soglia di similarità tra titoli (0-1)

# --- GESTIONE ARTICOLI GIÀ VISTI ---
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

# --- SIMILARITÀ TRA TITOLI ---
def normalize_title(title):
    """Rimuove punteggiatura, minuscolo, parole comuni."""
    stopwords = {"the", "a", "an", "is", "in", "on", "at", "to", "for",
                 "of", "and", "or", "but", "it", "its", "with", "how",
                 "why", "what", "who", "this", "that", "are", "was", "be"}
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    words = set(title.split()) - stopwords
    return words

def is_too_similar(new_title, posted_titles, threshold=SIMILARITY_THRESHOLD):
    """Controlla se il titolo è troppo simile a uno già postato."""
    new_words = normalize_title(new_title)
    if not new_words:
        return False
    for posted in posted_titles:
        posted_words = normalize_title(posted)
        if not posted_words:
            continue
        intersection = new_words & posted_words
        union = new_words | posted_words
        similarity = len(intersection) / len(union)
        if similarity >= threshold:
            return True
    return False

# --- FETCH E POST ---
async def check_feeds(bot, seen):
    new_seen = set()
    posts = []
    posted_titles = []  # titoli già pronti per essere postati in questo ciclo

    for url in FEED_URLS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            entry_id = entry.get("id") or entry.get("link")
            if not entry_id:
                continue
            new_seen.add(entry_id)
            if entry_id not in seen:
                title = entry.get("title", "Senza titolo")
                link = entry.get("link", "")
                source = feed.feed.get("title", "Fonte sconosciuta")

                # Controlla se il titolo è troppo simile a uno già in lista
                if is_too_similar(title, posted_titles):
                    print(f"[SKIP duplicato] {title}")
                    continue

                posted_titles.append(title)
                posts.append((title, link, source))

    for title, link, source in posts[:10]:
        text = f"💻 <b>{title}</b>\n🔗 {link}\n<i>via {source}</i>"
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                message_thread_id=TOPIC_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Errore nell'invio: {e}")

    return new_seen

# --- LOOP PRINCIPALE ---
async def main():
    bot = Bot(token=BOT_TOKEN)
    seen = load_seen()
    print(f"Bot avviato. Controllo ogni {CHECK_INTERVAL // 60} minuti.")

    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Controllo feed tech...")
        try:
            new_seen = await check_feeds(bot, seen)
            seen = seen.union(new_seen)
            save_seen(seen)
        except Exception as e:
            print(f"Errore generale: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
