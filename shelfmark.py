#!/usr/bin/env python3

"""
ShelfMark
Migrate Goodreads finished status to Audiobookshelf
"""

import argparse
import csv
import os
import sys

def main():
    parser = argparse.ArgumentParser(
        prog="ShelfMark",
        description="Migrate Goodreads finished status to Audiobookshelf",
    )

    parser.add_argument(
        "--goodreads-csv",
        required=True,
        help="Path to the Goodreads CSV export file"
    )

    parser.add_argument(
        "--abs-url",
        required=True,
        help="Audiobookshelf server URL (e.g., http://localhost:8080)"
    )

    parser.add_argument(
        "--abs-api-key",
        required=True,
        help="Audiobookshelf API key for authentication"
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to Audiobookshelf; without this flag, the script will run in dry-run mode"
    )

    args = parser.parse_args()

    csv_path = args.goodreads_csv

    if not os.path.isfile(csv_path):
        print(f"Error: Goodreads CSV file '{csv_path}' does not exist.")
        sys.exit(1)

    read_books = []

    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                shelf = (row.get('Exclusive Shelf') or '').strip().lower()
                if shelf == 'read':
                    read_books.append(row)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        sys.exit(1)


    print(f"Loaded Goodreads CSV: {len(read_books)} books marked as Read")

    if len(read_books) == 0:
        print("WARNING: No books marked as 'Read' were found.")

    if read_books:
        sample = read_books[0]
        print("Sample entry:")
        print(f"  Title: {sample.get('Title')}")
        print(f"  Author: {sample.get('Author')}")
        print()

    dry_run = not args.apply

    print("ShelfMark v0.1")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print()


if __name__ == "__main__":
    main()
