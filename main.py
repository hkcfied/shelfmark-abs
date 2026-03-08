from fastapi import FastAPI, UploadFile, Form, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
import io
import csv
from typing import Optional, List
from pydantic import BaseModel

import shelfmark

app = FastAPI(title="ShelfMark GUI")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://unpkg.com; "
            "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
            "font-src 'self' https://fonts.gstatic.com"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Serve the static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

# -----------------------------
# API Models
# -----------------------------

class ConnectRequest(BaseModel):
    abs_url: str
    api_key: str

class ApplyRequestItem(BaseModel):
    id: str

class ApplyRequest(BaseModel):
    abs_url: str
    api_key: str
    items: List[ApplyRequestItem]


# -----------------------------
# API Endpoints
# -----------------------------

@app.post("/api/connect")
def connect_abs(req: ConnectRequest):
    """
    Validate ABS credentials and return available libraries.
    """
    try:
        abs_url, headers, libraries = shelfmark.connect_to_abs_params(req.abs_url, req.api_key)
        # We don't want to expose our headers back to the client unnecessarily, just the libraries
        return {"status": "success", "libraries": libraries}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to connect to Audiobookshelf")

@app.post("/api/analyze")
async def analyze_csv(
    file: UploadFile,
    abs_url: str = Form(...),
    api_key: str = Form(...),
    library_id: str = Form(...)
):
    """
    Accepts the CSV and library selection, runs matching, returns preview.
    """
    try:
        # 1. Read the uploaded CSV
        contents = await file.read()
        csv_text = contents.decode("utf-8")
        read_books = shelfmark.load_goodreads_csv_from_string(csv_text)
        
        # 2. Connect to ABS and fetch items
        _, headers, _ = shelfmark.connect_to_abs_params(abs_url, api_key)
        raw_items = shelfmark.fetch_library_items(abs_url, headers, library_id)
        abs_items = shelfmark.normalize_abs_items(raw_items)
        
        # 3. Perform matching
        abs_isbn_index = shelfmark.index_abs_items_by_isbn(abs_items)
        isbn_matches, remaining = shelfmark.match_by_isbn(read_books, abs_isbn_index)

        abs_title_index = shelfmark.index_abs_items_by_title_author(abs_items)
        ta_matches, still_unmatched = shelfmark.match_by_title_author(remaining, abs_title_index)

        fuzzy_matches = []
        still_unmatched_final = []

        for book in still_unmatched:
            match = shelfmark.fuzzy_match_title_author(book, abs_items)
            if match:
                fuzzy_matches.append((book, match))
            else:
                still_unmatched_final.append(book)
        
        # Format the response for the frontend
        def format_matches(matches, match_type):
            return [
                {
                    "goodreads": {"title": gr.get("Title"), "author": gr.get("Author")},
                    "abs": {"id": abs_item.get("id"), "title": abs_item.get("title"), "author": abs_item.get("author")},
                    "type": match_type
                } for gr, abs_item in matches
            ]

        results = {
            "stats": {
                "total_read": len(read_books),
                "library_items": len(abs_items),
                "exact_isbn": len(isbn_matches),
                "exact_title_author": len(ta_matches),
                "fuzzy": len(fuzzy_matches),
                "unmatched": len(still_unmatched_final)
            },
            "matches": (
                format_matches(isbn_matches, "exact_isbn") +
                format_matches(ta_matches, "exact_title_author") +
                format_matches(fuzzy_matches, "fuzzy")
            ),
            "unmatched": [
                {"title": gr.get("Title"), "author": gr.get("Author")} 
                for gr in still_unmatched_final
            ]
        }
        
        return JSONResponse({"status": "success", "data": results})

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Analysis failed")

@app.post("/api/apply")
def apply_changes(req: ApplyRequest):
    """
    Mark the selected items as finished in ABS.
    """
    try:
        _, headers, _ = shelfmark.connect_to_abs_params(req.abs_url, req.api_key)
        
        success_count = 0
        failed_count = 0
        errors = []

        for item in req.items:
            ok, error = shelfmark.mark_item_finished(req.abs_url, headers, item.id)
            if ok:
                success_count += 1
            else:
                failed_count += 1
                errors.append({"id": item.id, "error": error})
        
        return {
            "status": "success", 
            "summary": {
                "success": success_count,
                "failed": failed_count,
                "errors": errors
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to apply changes")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
