# ShelfMark

**Migrate Goodreads finished status to Audiobookshelf**

ShelfMark is a one-time migration tool that imports books marked as **Read** in a Goodreads CSV export and marks the corresponding audiobooks as **Finished** in Audiobookshelf.

This project is intended for users migrating an existing audiobook library and goodreads reading history to Audiobookshelf.
It does **not** provide live syncing, background updates, or progress tracking.

---

## What ShelfMark does

- Reads a Goodreads library export (CSV)
- Matches books to your Audiobookshelf library
- Marks matched books as _Finished_
- Supports dry-run mode for safety

## What ShelfMark does NOT do

- No live or bidirectional syncing
- No reading progress import
- No need of Goodreads login or API
- No audio file or metadata modification

## Requirements

- Python 3.9+
- Audiobookshelf server with API access
- Goodreads CSV export

## Project status

Early development (v0.1).  
Feedback and contributions are welcome.
