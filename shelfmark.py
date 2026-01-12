#!/usr/bin/env python3

"""
ShelfMark
Migrate Goodreads finished status to Audiobookshelf
(Current stage: interactive, read-only)
"""

import csv
import os
import sys
import requests
import re
import difflib


# -----------------------------
# Utility helpers
# -----------------------------

def prompt(message):
    return input(message).strip()


def fatal(message):
    print(f"ERROR: {message}")
    sys.exit(1)

# -----------------------------
# Normalization helpers
# -----------------------------

def normalize_isbn(value):
    if not value:
        return None
    digits = "".join(c for c in value if c.isdigit())
    return digits if digits else None

def normalize_text(value):
    if not value:
        return None

    value = value.lower().strip()

    # Remove trailing series info in parentheses or brackets
    value = re.sub(r"\s*[\(\[].*?[\)\]]\s*$", "", value)

    # Remove punctuation
    value = re.sub(r"[^\w\s]", "", value)

    # Normalize whitespace
    value = re.sub(r"\s+", " ", value)

    return value.strip()


# -----------------------------
# Step 1: Goodreads CSV
# -----------------------------

def load_goodreads_csv():
    path = prompt("Enter path to Goodreads CSV export: ")

    if not os.path.isfile(path):
        fatal(f"File not found: {path}")

    read_books = []

    try:
        with open(path, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)

            if "Exclusive Shelf" not in reader.fieldnames:
                fatal("CSV does not appear to be a valid Goodreads export")

            for row in reader:
                shelf = (row.get("Exclusive Shelf") or "").strip().lower()
                if shelf == "read":
                    read_books.append(row)

    except Exception as e:
        fatal(f"Failed to read CSV: {e}")

    print(f"Loaded Goodreads CSV: {len(read_books)} books marked as Read")

    if read_books:
        sample = read_books[0]
        print("Sample Goodreads entry:")
        print(f"  Title: {sample.get('Title')}")
        print(f"  Author: {sample.get('Author')}")
        print()

    return read_books


# -----------------------------
# Step 2: Connect to ABS
# -----------------------------

def connect_to_abs():
    abs_url = prompt(
        "Enter Audiobookshelf base URL (e.g. http://localhost:13378): "
    ).rstrip("/")

    api_key = prompt("Enter Audiobookshelf API key: ")

    if not abs_url.startswith("http"):
        fatal("Audiobookshelf URL must start with http:// or https://")

    if not api_key:
        fatal("API key cannot be empty")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            f"{abs_url}/api/libraries",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        fatal(f"Failed to connect to Audiobookshelf API: {e}")

    payload = response.json()
    libraries = payload.get("libraries", [])

    if not isinstance(libraries, list) or not libraries:
        fatal("No libraries found on Audiobookshelf server")

    print(f"[DEBUG] Retrieved {len(libraries)} libraries from Audiobookshelf")

    return abs_url, headers, libraries


# -----------------------------
# Step 3: Library selection
# -----------------------------

def select_library(libraries):
    print("\nAvailable libraries:")

    for idx, lib in enumerate(libraries, start=1):
        print(f"[{idx}] {lib.get('name')}")

    while True:
        choice = prompt("Select a library by number: ")

        if not choice.isdigit():
            print("Please enter a number.")
            continue

        idx = int(choice)
        if 1 <= idx <= len(libraries):
            selected = libraries[idx - 1]
            print(f"Selected library: {selected.get('name')}\n")
            return selected

        print("Invalid selection. Try again.")


# -----------------------------
# Step 4: Fetch library items
# -----------------------------

def fetch_library_items(abs_url, headers, library_id):
    try:
        response = requests.get(
            f"{abs_url}/api/libraries/{library_id}/items",
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as e:
        fatal(f"Failed to fetch library items: {e}")

    print("[DEBUG] HTTP status:", response.status_code)
    print("[DEBUG] Raw response text (first 500 chars):")
    print(response.text[:500])

    payload = response.json()
    items = (
        payload.get("results")
        or payload.get("libraryItems")
        or payload.get("items")
        or []
    )


    print("[DEBUG] Parsed item count:", len(items))

    return items



# -----------------------------
# Step 5: Normalize ABS items
# -----------------------------

def normalize_abs_items(items):
    normalized = []

    for item in items:
        media = item.get("media") or {}
        metadata = media.get("metadata") or {}

        normalized.append({
            "id": item.get("id"),
            "title": metadata.get("title"),
            "author": metadata.get("authorName"),
            "isbn": metadata.get("isbn"),
            "asin": metadata.get("asin"),
        })

    return normalized

# -----------------------------
#  Index ABS items by ISBN
# -----------------------------

def index_abs_items_by_isbn(abs_items):
    index = {}

    for item in abs_items:
        isbn = normalize_isbn(item.get("isbn"))
        if isbn:
            index[isbn] = item

    return index

# -----------------------------
#  Step 6: Match Goodreads books to ABS items
# -----------------------------

def match_by_isbn(goodreads_books, abs_index):
    matches = []
    unmatched = []

    for book in goodreads_books:
        isbn13 = normalize_isbn(book.get("ISBN13"))
        isbn10 = normalize_isbn(book.get("ISBN"))

        match = None

        if isbn13 and isbn13 in abs_index:
            match = abs_index[isbn13]
        elif isbn10 and isbn10 in abs_index:
            match = abs_index[isbn10]

        if match:
            matches.append((book, match))
        else:
            unmatched.append(book)

    return matches, unmatched

def index_abs_items_by_title_author(abs_items):
    index = {}

    for item in abs_items:
        title = normalize_text(item.get("title"))
        author = normalize_text(item.get("author"))

        if not title or not author:
            continue

        key = (title, author)
        index.setdefault(key, []).append(item)

    return index


def match_by_title_author(goodreads_books, abs_index):
    matches = []
    unmatched = []

    for book in goodreads_books:
        title = normalize_text(book.get("Title"))
        author = normalize_text(book.get("Author"))

        if not title or not author:
            unmatched.append(book)
            continue

        candidates = abs_index.get((title, author), [])

        if len(candidates) == 1:
            matches.append((book, candidates[0]))
        else:
            unmatched.append(book)

    return matches, unmatched

def similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def fuzzy_match_title_author(book, abs_items):
    gr_title = normalize_text(book.get("Title"))
    gr_author = normalize_text(book.get("Author"))

    if not gr_title or not gr_author:
        return None

    candidates = []

    for item in abs_items:
        abs_title = normalize_text(item.get("title"))
        abs_author = normalize_text(item.get("author"))

        if not abs_title or not abs_author:
            continue

        title_score = similarity(gr_title, abs_title)
        author_score = similarity(gr_author, abs_author)

        # Strict thresholds
        if title_score >= 0.9 and author_score >= 0.85:
            candidates.append((title_score + author_score, item))

    if len(candidates) == 1:
        return candidates[0][1]

    return None

def preview_finish_updates(matches):
    print("\nPreview: items that would be marked as finished\n")

    for idx, (gr, abs_item) in enumerate(matches, start=1):
        print(f"[{idx}] {abs_item.get('title')} — {abs_item.get('author')}")
        print(f"     Goodreads: {gr.get('Title')} by {gr.get('Author')}")



# -----------------------------
# Main program flow
# -----------------------------

def main():
    print("ShelfMark v0.1")
    print("Mode: DRY RUN (no changes will be made)")
    print()

    # Step 1
    read_books = load_goodreads_csv()

    # Step 2
    abs_url, headers, libraries = connect_to_abs()

    # Step 3
    library = select_library(libraries)

    # Step 4
    raw_items = fetch_library_items(abs_url, headers, library.get("id"))
    abs_items = normalize_abs_items(raw_items)

    print(f"\nFetched {len(abs_items)} items from library")

    if abs_items:
        sample = abs_items[0]
        print("Sample library item:")
        print(f"  Title: {sample['title']}")
        print(f"  Author: {sample['author']}")
        print()

    print("Setup complete.")
    print("Next step will match Goodreads books to this library.")
    print("No changes have been made.")

    # Step 5: Match by ISBN
    # ISBN matching
    abs_isbn_index = index_abs_items_by_isbn(abs_items)
    isbn_matches, remaining = match_by_isbn(read_books, abs_isbn_index)

    # Title + author matching
    abs_title_index = index_abs_items_by_title_author(abs_items)
    ta_matches, still_unmatched = match_by_title_author(remaining, abs_title_index)

    # Fuzzy matching for remaining books
    fuzzy_matches = []
    still_unmatched_final = []

    for book in still_unmatched:
        match = fuzzy_match_title_author(book, abs_items)
        if match:
            fuzzy_matches.append((book, match))
        else:
            still_unmatched_final.append(book)

    all_matches = isbn_matches + ta_matches + fuzzy_matches

    print(f"Matched by ISBN: {len(isbn_matches)}")
    print(f"Matched by title/author: {len(ta_matches)}")
    print(f"Matched by fuzzy logic: {len(fuzzy_matches)}")
    print(f"Total matched: {len(all_matches)}")
    print(f"Still unmatched: {len(still_unmatched_final)}")

    # Step 11: Dry-run preview
    preview_finish_updates(all_matches)

    print("\nDRY RUN complete.")
    print("No changes have been applied.")

if __name__ == "__main__":
    main()
