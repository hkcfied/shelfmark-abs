"""
Integration tests for the FastAPI endpoints in main.py.

External calls (shelfmark.connect_to_abs_params, shelfmark.fetch_library_items,
shelfmark.mark_item_finished) are mocked to avoid real network I/O.
"""

import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FAKE_LIBRARIES = [{"id": "lib1", "name": "Audiobook"}, {"id": "lib2", "name": "Podcast"}]
FAKE_HEADERS = {"Authorization": "Bearer testkey", "Accept": "application/json"}

GOODREADS_CSV = (
    "Book Id,Title,Author,Author l-f,Additional Authors,"
    "ISBN,ISBN13,My Rating,Average Rating,Publisher,Binding,"
    "Number of Pages,Year Published,Original Publication Year,"
    "Date Read,Date Added,Bookshelves,Bookshelves with positions,"
    "Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies\n"
    '1,"Dune","Frank Herbert","Herbert, Frank",,="0441013597",="9780441013594",'
    "5,4.26,Ace,Paperback,412,1965,1965,2023/01/01,2023/01/01,,shelf,read,,,,1,0\n"
)

FAKE_RAW_ITEMS = [
    {
        "id": "abs-item-1",
        "media": {
            "metadata": {
                "title": "Dune",
                "authorName": "Frank Herbert",
                "isbn": "9780441013594",
                "asin": None,
            }
        }
    }
]


# ---------------------------------------------------------------------------
# POST /api/connect
# ---------------------------------------------------------------------------

class TestConnectEndpoint:
    def test_returns_libraries_on_success(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)):
            resp = client.post("/api/connect", json={"abs_url": "http://localhost", "api_key": "key"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["libraries"] == FAKE_LIBRARIES

    def test_passes_credentials_to_shelfmark(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)) as mock_fn:
            client.post("/api/connect", json={"abs_url": "http://localhost:13378", "api_key": "mykey"})
        mock_fn.assert_called_once_with("http://localhost:13378", "mykey")

    def test_returns_400_on_invalid_url(self):
        with patch("shelfmark.connect_to_abs_params", side_effect=ValueError("must start with http")):
            resp = client.post("/api/connect", json={"abs_url": "ftp://bad", "api_key": "key"})
        assert resp.status_code == 400
        assert "must start with http" in resp.json()["detail"]

    def test_returns_400_on_connection_failure(self):
        with patch("shelfmark.connect_to_abs_params", side_effect=ValueError("Failed to connect")):
            resp = client.post("/api/connect", json={"abs_url": "http://unreachable", "api_key": "key"})
        assert resp.status_code == 400

    def test_missing_api_key_field_returns_422(self):
        resp = client.post("/api/connect", json={"abs_url": "http://localhost"})
        assert resp.status_code == 422

    def test_missing_abs_url_field_returns_422(self):
        resp = client.post("/api/connect", json={"api_key": "key"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/analyze
# ---------------------------------------------------------------------------

class TestAnalyzeEndpoint:
    def _post_analyze(self, csv_content=None, abs_url="http://localhost", api_key="key", library_id="lib1"):
        csv_bytes = (GOODREADS_CSV if csv_content is None else csv_content).encode("utf-8")
        return client.post(
            "/api/analyze",
            data={"abs_url": abs_url, "api_key": api_key, "library_id": library_id},
            files={"file": ("export.csv", io.BytesIO(csv_bytes), "text/csv")},
        )

    def test_returns_matched_books_on_success(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.fetch_library_items", return_value=FAKE_RAW_ITEMS):
            resp = self._post_analyze()
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        stats = data["data"]["stats"]
        assert stats["total_read"] == 1

    def test_isbn_match_counted_correctly(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.fetch_library_items", return_value=FAKE_RAW_ITEMS):
            resp = self._post_analyze()
        stats = resp.json()["data"]["stats"]
        # Dune ISBN13 matches → counted as exact_isbn
        assert stats["exact_isbn"] >= 1

    def test_returns_400_for_invalid_csv(self):
        bad_csv = "Title,Author\nDune,Frank Herbert\n"
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.fetch_library_items", return_value=FAKE_RAW_ITEMS):
            resp = self._post_analyze(csv_content=bad_csv)
        assert resp.status_code == 400
        assert "Goodreads" in resp.json()["detail"]

    def test_returns_400_on_abs_connection_failure(self):
        with patch("shelfmark.connect_to_abs_params", side_effect=ValueError("Failed to connect")):
            resp = self._post_analyze()
        assert resp.status_code == 400

    def test_unmatched_books_included_in_response(self):
        # ABS has no items → everything unmatched
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.fetch_library_items", return_value=[]):
            resp = self._post_analyze()
        data = resp.json()["data"]
        assert data["stats"]["unmatched"] == 1
        assert len(data["unmatched"]) == 1

    def test_empty_csv_returns_400(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.fetch_library_items", return_value=FAKE_RAW_ITEMS):
            resp = self._post_analyze(csv_content="")
        assert resp.status_code == 400

    def test_response_structure_is_complete(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.fetch_library_items", return_value=FAKE_RAW_ITEMS):
            resp = self._post_analyze()
        data = resp.json()["data"]
        assert "stats" in data
        assert "matches" in data
        assert "unmatched" in data
        stats = data["stats"]
        for key in ("total_read", "library_items", "exact_isbn", "exact_title_author", "fuzzy", "unmatched"):
            assert key in stats

    def test_match_items_have_required_fields(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.fetch_library_items", return_value=FAKE_RAW_ITEMS):
            resp = self._post_analyze()
        matches = resp.json()["data"]["matches"]
        if matches:
            m = matches[0]
            assert "goodreads" in m
            assert "abs" in m
            assert "type" in m
            assert "id" in m["abs"]


# ---------------------------------------------------------------------------
# POST /api/apply
# ---------------------------------------------------------------------------

class TestApplyEndpoint:
    def _post_apply(self, items=None, abs_url="http://localhost", api_key="key"):
        return client.post(
            "/api/apply",
            json={
                "abs_url": abs_url,
                "api_key": api_key,
                "items": items if items is not None else [{"id": "abs-item-1"}],
            },
        )

    def test_marks_items_finished_successfully(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.mark_item_finished", return_value=(True, None)):
            resp = self._post_apply()
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        assert summary["success"] == 1
        assert summary["failed"] == 0

    def test_reports_partial_failures(self):
        responses = [(True, None), (False, "timeout")]
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.mark_item_finished", side_effect=responses):
            resp = self._post_apply(items=[{"id": "item1"}, {"id": "item2"}])
        summary = resp.json()["summary"]
        assert summary["success"] == 1
        assert summary["failed"] == 1
        assert len(summary["errors"]) == 1

    def test_errors_include_item_id(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.mark_item_finished", return_value=(False, "server error")):
            resp = self._post_apply(items=[{"id": "broken-item"}])
        errors = resp.json()["summary"]["errors"]
        assert errors[0]["id"] == "broken-item"

    def test_calls_mark_finished_for_each_item(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.mark_item_finished", return_value=(True, None)) as mock_mark:
            self._post_apply(items=[{"id": "a"}, {"id": "b"}, {"id": "c"}])
        assert mock_mark.call_count == 3

    def test_returns_400_on_connection_failure(self):
        with patch("shelfmark.connect_to_abs_params", side_effect=ValueError("Failed to connect")):
            resp = self._post_apply()
        assert resp.status_code == 400

    def test_missing_items_field_returns_422(self):
        resp = client.post("/api/apply", json={"abs_url": "http://localhost", "api_key": "key"})
        assert resp.status_code == 422

    def test_empty_items_list_applies_nothing(self):
        with patch("shelfmark.connect_to_abs_params", return_value=("http://localhost", FAKE_HEADERS, FAKE_LIBRARIES)), \
             patch("shelfmark.mark_item_finished", return_value=(True, None)) as mock_mark:
            resp = self._post_apply(items=[])
        assert resp.status_code == 200
        assert mock_mark.call_count == 0
        assert resp.json()["summary"]["success"] == 0
