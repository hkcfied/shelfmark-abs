#!/usr/bin/env python3

"""
ShelfMark
Migrate Goodreads finished status to Audiobookshelf
"""

import argparse

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

    dry_run = not args.apply

    print("ShelfMark v0.1")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print()


if __name__ == "__main__":
    main()
