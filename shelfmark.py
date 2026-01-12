#!/usr/bin/env python3

"""
ShelfMark
Migrate Goodreads finished status to Audiobookshelf
"""

import csv
import os
import sys
import requests
import re
import difflib
import argparse


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

    # Remove subtitles
    value = value.split(":")[0]

    # Remove trailing series info
    value = re.sub(r"\s*[\(\[].*?[\)\]]\s*$", "", value)

    # Remove punctuation
    value = re.sub(r"[^\w\s]", "", value)

    # Normalize whitespace
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


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
        response.raise_for_status()
    except requests.RequestException as e:
        fatal(f"Failed to fetch library items: {e}")

    payload = response.json()

    items = (
        payload.get("results")
        or payload.get("libraryItems")
        or payload.get("items")
        or []
    )

    if not isinstance(items, list):
        fatal("Unexpected Audiobookshelf items response")

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
# Matching helpers
# -----------------------------

def index_abs_items_by_isbn(abs_items):
    index = {}

    for item in abs_items:
        isbn = normalize_isbn(item.get("isbn"))
        if isbn:
            index[isbn] = item

    return index


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

        if similarity(gr_title, abs_title) >= 0.9 and similarity(gr_author, abs_author) >= 0.85:
            candidates.append(item)

    return candidates[0] if len(candidates) == 1 else None


# -----------------------------
# Apply helpers
# -----------------------------

def preview_finish_updates(matches):
    print("\nPreview: items that would be marked as finished\n")

    for idx, (gr, abs_item) in enumerate(matches, start=1):
        print(f"[{idx}] {abs_item.get('title')} — {abs_item.get('author')}")
        print(f"     Goodreads: {gr.get('Title')} by {gr.get('Author')}")


def mark_item_finished(abs_url, headers, library_item_id):
    try:
        response = requests.patch(
            f"{abs_url}/api/me/progress/batch/update",
            headers={**headers, "Content-Type": "application/json"},
            json=[{
                "libraryItemId": library_item_id,
                "isFinished": True,
            }],
            timeout=30,
        )
        response.raise_for_status()
        return True, None
    except requests.RequestException as e:
        return False, str(e)




# -----------------------------
# Argument parsing
# -----------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Migrate Goodreads finished status to Audiobookshelf"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (mark matched audiobooks as finished)"
    )
    return parser.parse_args()


# -----------------------------
# Main
# -----------------------------

def main():
    args = parse_args()

    print("ShelfMark v0.1")
    print("Mode:", "APPLY" if args.apply else "DRY RUN")
    print()

    read_books = load_goodreads_csv()
    abs_url, headers, libraries = connect_to_abs()
    library = select_library(libraries)

    raw_items = fetch_library_items(abs_url, headers, library.get("id"))
    abs_items = normalize_abs_items(raw_items)

    print(f"\nFetched {len(abs_items)} items from library")

    abs_isbn_index = index_abs_items_by_isbn(abs_items)
    isbn_matches, remaining = match_by_isbn(read_books, abs_isbn_index)

    abs_title_index = index_abs_items_by_title_author(abs_items)
    ta_matches, still_unmatched = match_by_title_author(remaining, abs_title_index)

    fuzzy_matches = []
    still_unmatched_final = []

    for book in still_unmatched:
        match = fuzzy_match_title_author(book, abs_items)
        if match:
            fuzzy_matches.append((book, match))
        else:
            still_unmatched_final.append(book)

    all_matches = isbn_matches + ta_matches + fuzzy_matches

    print(f"\nMatched by ISBN: {len(isbn_matches)}")
    print(f"Matched by title/author: {len(ta_matches)}")
    print(f"Matched by fuzzy logic: {len(fuzzy_matches)}")
    print(f"Total matched: {len(all_matches)}")
    print(f"Still unmatched: {len(still_unmatched_final)}")

    preview_finish_updates(all_matches)

    if not args.apply:
        print("\nDRY RUN complete.")
        print("Re-run with --apply to mark items as finished.")
        return

    confirm = input(
        "\nThis will mark the above items as FINISHED in Audiobookshelf.\n"
        "Type 'yes' to continue: "
    ).strip().lower()

    if confirm != "yes":
        print("Aborted. No changes made.")
        return

    print("\nApplying updates...\n")

    success = 0
    failed = 0

    for _, abs_item in all_matches:
        ok, error = mark_item_finished(abs_url, headers, abs_item["id"])
        if ok:
            success += 1
            print(f"[OK] {abs_item['title']}")
        else:
            failed += 1
            print(f"[FAIL] {abs_item['title']}: {error}")

    print("\nApply complete.")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
