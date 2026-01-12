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


# -----------------------------
# Utility helpers
# -----------------------------

def prompt(message):
    return input(message).strip()


def fatal(message):
    print(f"ERROR: {message}")
    sys.exit(1)


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


if __name__ == "__main__":
    main()
