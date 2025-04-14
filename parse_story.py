
import os
import re
import json
import requests
import argparse
from bs4 import BeautifulSoup
from collections import Counter
from datetime import datetime
import subprocess

LIBRARY_PATH = "./library.json"
CONTENT_DIR = "./content"

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
    words = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
    blacklist = {"Chapter", "Project", "Gutenberg", "This", "That", "From", "With", "Table", "About", "Above", "Below", "More", "Less", "Other"}
    filtered = [word for word in words if word not in blacklist]
    freq = Counter(filtered)
    top_names = [name for name, count in freq.most_common(10) if count > 2]
    characters = [{
        "name": name,
        "description": f"{name} is a recurring character who appears to play a key role in the narrative."
    } for name in top_names]
    return characters

def get_cover_image(url):
    base_url = url.rsplit('/', 1)[0]
    return base_url + "/images/cover.jpg"

def clean_title(raw_title):
    title = raw_title.replace("The Project Gutenberg eBook of", "").split(", by")[0].strip()
    return title

def clean_author(raw_author):
    author = raw_author.replace("by", "").strip()
    author = re.sub(r"\[.*?\]", "", author).strip()
    return author

def generate_summary(text):
    sentences = re.split(r'(?<=[.!?]) +', text)
    for sentence in sentences:
        if len(sentence.split()) > 6:
            return sentence.strip()
    return "A story about imagination, adventure, and transformation."

def parse_gutenberg_html(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    raw_title = soup.find('title').text.strip()
    raw_author = soup.find('h2').text.strip() if soup.find('h2') else "Unknown"

    title = clean_title(raw_title)
    author = clean_author(raw_author)

    raw_text = soup.get_text(separator=' ', strip=True)
    word_count = len(raw_text.split())

    summary = generate_summary(raw_text)

    story_data = {
        "title": title,
        "author": author,
        "year": datetime.now().year,
        "category": detect_category(raw_text),
        "cover_image": get_cover_image(url),
        "link": url,
        "summary": summary,
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
            ch_title = match.group(0).strip()
            chapters[ch_title] = raw_text[start:end].strip()
    else:
        chapters["Full Story"] = raw_text

    return story_data, chapters

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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', type=str, required=True, help='Gutenberg story URL')
    args = parser.parse_args()
    url = args.url

    library = load_library()
    existing_index = next((i for i, entry in enumerate(library) if entry["link"] == url), None)

    if existing_index is not None:
        choice = input("⚠️ This story already exists. Do you want to overwrite it? (y/n): ").strip().lower()
        if choice != 'y':
            print("❌ Cancelled. Please enter a new URL.")
            return
        else:
            print("🔁 Overwriting existing story...")

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

    if existing_index is not None:
        library[existing_index] = metadata
    else:
        library.append(metadata)

    save_library(library)
    commit_and_push(metadata["title"])
    print("✅ Story saved and pushed to GitHub.")

if __name__ == "__main__":
    main()
