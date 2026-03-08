# ShelfMark

**Migrate Goodreads finished status to Audiobookshelf**

ShelfMark is a one-time migration tool that imports books marked as **Read** in a Goodreads CSV export and marks the corresponding audiobooks as **Finished** in your Audiobookshelf library.

Since its creation, ShelfMark has evolved to offer both a clean, step-by-step **GUI application** and a fast, scriptable **CLI tool**. Both methods share the same robust matching algorithm and ensure complete safety with purely read-only dry runs.

It does **not** provide live syncing, background updates, or progress tracking.

---

## Features

- **Intuitive GUI & Fast CLI**: Choose between an easy-to-use web interface and a fast command-line terminal interface.
- **Smart Matching Algorithm**: Finds your books using a robust three-tier matching system:
  1. **Exact ISBN match**: Highly accurate matching using Goodreads ISBN/ISBN13 against ABS identifiers.
  2. **Exact Title & Author match**: Fallback for books without matching ISBNs.
  3. **Fuzzy Matching**: Intelligent matching for slight variations in titles or author names (e.g., "J. R. R. Tolkien" vs "J.R.R. Tolkien").
- **Review Before Apply**: Provides a comprehensive preview of matched and unmatched items, ensuring absolute safety. **No changes are made without your explicit confirmation**.
- **Library Selection**: Supports selecting specific libraries within your Audiobookshelf server.

## What ShelfMark does NOT do

- No live or bidirectional syncing
- No reading progress import
- No need for Goodreads login or API access
- No audio file or internal metadata modification

## Requirements

- Python 3.9+
- Audiobookshelf server with API access (API key required)
- Goodreads CSV export (Your library export)

## Installation & Configuration

1. **Install dependencies**: Make sure you have the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
2. **Configuration file (Optional but Recommended)**: Create a `config.yml` in the project root to save your connection settings. This pre-fills the GUI fields and bypasses interactive prompts in the CLI.
   ```yaml
   abs_url: http://localhost:13378
   api_key: your_api_key_here
   library_name: Audiobook
   csv_path: path/to/your/goodreads_library_export.csv
   ```

## Usage

### Using the GUI (Recommended)
The GUI offers a visual wizard to upload your CSV, preview results, and selectively apply changes.

1. **Start the server**: Run the FastAPI server locally:
   ```bash
   python main.py
   ```
   *Alternatively, you can run it with `uvicorn main:app --reload` for development.*
2. **Open the App**: Navigate to `http://127.0.0.1:8000` in your web browser and follow the on-screen instructions.

### Using the CLI
The CLI is perfect for quick runs directly from your terminal. It always performs a dry run first.

1. **Run a Dry Run**: Test the matching algorithm and view a preview of changes without altering anything.
   ```bash
   python shelfmark.py
   ```
2. **Apply Changes**: After reviewing the dry run, add the `--apply` flag to commit the "Finished" status to the matched books in Audiobookshelf.
   ```bash
   python shelfmark.py --apply
   ```

## Project status

Early development (v0.2).  
Feedback and contributions are welcome.
