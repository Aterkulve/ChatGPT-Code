
import os
import re
import json
import requests
import argparse
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
import subprocess

# --- CONFIG ---
LIBRARY_PATH = "./library.json"
CONTENT_DIR = "./content"

# --- UTILITIES ---

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')

def estimate_reading_time(word_count):
    wpm = 200
    minutes = word_count // wpm
    return f"~{max(1, minutes)} min"

def detect_age_category(word_count):
    if word_count < 1000:
        return "5–8"
    elif word_count < 5000:
        return "6–10"
    elif word_count < 15000:
        return "8–12"
    else:
        return "10–14"

def detect_category(text):
    themes = {
        "Morality & Cautionary Lessons": ["foolish", "wise", "lesson", "moral", "punish"],
        "Actions & Consequences": ["consequence", "result", "choice", "action", "regret"],
        "Empathy & Transformation": ["feel", "change", "understand", "kind", "transform"],
        "Friendship & Loyalty": ["friend", "loyal", "trust", "help", "together"],
        "Growing Up & Responsibility": ["child", "grow", "responsible", "adult", "learn"],
        "Curiosity & Imagination": ["dream", "imagine", "wonder", "explore", "magic"]
    }
    for category, keywords in themes.items():
        if any(word in text.lower() for word in keywords):
            return category
    return "Curiosity & Imagination"

def extract_characters(text):
    sentences = re.split(r'(?<=[.!?]) +', text)
    names = set()
    for sentence in sentences:
        for match in re.finditer(r'\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b', sentence):
            if match:
                names.add(match.group(0))
    characters = []
    for name in sorted(names):
        characters.append({
            "name": name,
            "description": f"{name} appears in the story and plays a role that reflects their motivations or growth."
        })
    return characters[:10]

def get_cover_image(url):
    base_url = url.rsplit('/', 1)[0]
    return base_url + "/images/cover.jpg"

# --- PARSER ---

def parse_gutenberg_html(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    title = soup.find('title').text.strip()
    author = soup.find('h2')
    author = author.text.strip() if author else "Unknown"

    raw_text = soup.get_text(separator=' ', strip=True)
    word_count = len(raw_text.split())

    story_data = {
        "title": title,
        "author": author,
        "year": datetime.now().year,
        "category": detect_category(raw_text),
        "cover_image": get_cover_image(url),
        "link": url,
        "summary": f"A story titled '{title}' written by {author}.",
        "reading_time": estimate_reading_time(word_count),
        "age_category": detect_age_category(word_count),
        "characters": extract_characters(raw_text),
    }

    chapters = {}
    matches = list(re.finditer(r'(Chapter\s+\w+|CHAPTER\s+\w+)', raw_text))
    if matches:
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)
            title = match.group(0).strip()
            content = raw_text[start:end].strip()
            chapters[title] = content
    else:
        chapters["Full Story"] = raw_text

    return story_data, chapters

# --- FILE HANDLING ---

def load_library():
    if not os.path.exists(LIBRARY_PATH):
        return []
    with open(LIBRARY_PATH, "r") as f:
        return json.load(f)

def save_library(library):
    with open(LIBRARY_PATH, "w") as f:
        json.dump(library, f, indent=2)

def save_story(slug, content):
    os.makedirs(CONTENT_DIR, exist_ok=True)
    with open(os.path.join(CONTENT_DIR, f"{slug}.json"), "w") as f:
        json.dump(content, f, indent=2)

def commit_and_push(title):
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", f"Added/Updated story: {title}"], check=True)
    subprocess.run(["git", "push"], check=True)

# --- MAIN SCRIPT ---

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', type=str, required=True, help='Gutenberg story URL')
    args = parser.parse_args()
    url = args.url

    library = load_library()
    for entry in library:
        if entry["link"] == url:
            print("⚠️  This story or collection already exists in your library. Please enter a new URL.")
            return

    print("🔍 Parsing story...")
    metadata, content = parse_gutenberg_html(url)
    slug = slugify(metadata["title"])

    print(f"✅ Parsed: {metadata['title']}")
    print(f"📖 Type: {'collection' if len(content) > 5 else 'story'}")
    print(f"🕒 Reading time: {metadata['reading_time']}")
    print(f"🎯 Category: {metadata['category']}")
    print(f"👤 Characters: {[c['name'] for c in metadata['characters']]}")
    print(f"🧠 Age category: {metadata['age_category']}")

    save_story(slug, content)
    library.append(metadata)
    save_library(library)

    commit_and_push(metadata["title"])
    print("✅ Story saved and pushed to GitHub.")

if __name__ == "__main__":
    main()
