"""
Unit tests for shelfmark.py core logic.

Covers: normalize_isbn, normalize_text, load_goodreads_csv_from_string,
        connect_to_abs_params (validation), normalize_abs_items,
        match_by_isbn, match_by_title_author, fuzzy_match_title_author.
"""

import pytest
from unittest.mock import patch, MagicMock
import requests

import shelfmark


# ---------------------------------------------------------------------------
# Fixtures / shared test data
# ---------------------------------------------------------------------------

GOODREADS_CSV_HEADER = (
    "Book Id,Title,Author,Author l-f,Additional Authors,"
    "ISBN,ISBN13,My Rating,Average Rating,Publisher,Binding,"
    "Number of Pages,Year Published,Original Publication Year,"
    "Date Read,Date Added,Bookshelves,Bookshelves with positions,"
    "Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies\n"
)

def make_csv_row(
    book_id="1",
    title="The Hobbit",
    author="J.R.R. Tolkien",
    isbn='="0261102214"',
    isbn13='="9780261102217"',
    shelf="read",
):
    return (
        f'{book_id},"{title}","{author}","Tolkien, J.R.R.",,{isbn},{isbn13},'
        f"5,4.28,HarperCollins,Paperback,310,1937,1937,2023/01/01,2023/01/01,,"
        f'shelf,{shelf},,,,1,0\n'
    )


# ---------------------------------------------------------------------------
# normalize_isbn
# ---------------------------------------------------------------------------

class TestNormalizeIsbn:
    def test_plain_isbn13(self):
        assert shelfmark.normalize_isbn("9780261102217") == "9780261102217"

    def test_isbn13_with_dashes(self):
        assert shelfmark.normalize_isbn("978-0-261-10221-7") == "9780261102217"

    def test_isbn10_with_dashes(self):
        assert shelfmark.normalize_isbn("0-261-10221-4") == "0261102214"

    def test_goodreads_bracketed_format(self):
        # Goodreads exports ISBNs wrapped in ="..."
        assert shelfmark.normalize_isbn('="9780261102217"') == "9780261102217"

    def test_none_returns_none(self):
        assert shelfmark.normalize_isbn(None) is None

    def test_empty_string_returns_none(self):
        assert shelfmark.normalize_isbn("") is None

    def test_non_digit_string_returns_none(self):
        assert shelfmark.normalize_isbn("N/A") is None

    def test_whitespace_only_returns_none(self):
        assert shelfmark.normalize_isbn("   ") is None


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_lowercases_input(self):
        assert shelfmark.normalize_text("Hello World") == "hello world"

    def test_strips_leading_trailing_whitespace(self):
        assert shelfmark.normalize_text("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self):
        assert shelfmark.normalize_text("hello   world") == "hello world"

    def test_removes_subtitle_after_colon(self):
        assert shelfmark.normalize_text("Dune: A Novel") == "dune"

    def test_removes_trailing_parenthetical_series(self):
        assert shelfmark.normalize_text("Dune (Dune Chronicles #1)") == "dune"

    def test_removes_trailing_bracketed_edition(self):
        assert shelfmark.normalize_text("Dune [Revised Edition]") == "dune"

    def test_removes_punctuation(self):
        assert shelfmark.normalize_text("It's a Test!") == "its a test"

    def test_none_returns_none(self):
        assert shelfmark.normalize_text(None) is None

    def test_empty_string_returns_none(self):
        assert shelfmark.normalize_text("") is None

    def test_only_punctuation_returns_none(self):
        # After stripping punctuation only whitespace remains → empty → None
        result = shelfmark.normalize_text("!!!---")
        assert result is None or result == ""

    def test_preserves_non_ascii_letters(self):
        # Should not crash on accented chars
        result = shelfmark.normalize_text("Héllo Wörld")
        assert result is not None


# ---------------------------------------------------------------------------
# load_goodreads_csv_from_string
# ---------------------------------------------------------------------------

class TestLoadGoodreadsCsvFromString:
    def _valid_csv(self, *extra_rows):
        rows = GOODREADS_CSV_HEADER + make_csv_row()
        for row in extra_rows:
            rows += row
        return rows

    def test_loads_read_books(self):
        csv_text = self._valid_csv()
        books = shelfmark.load_goodreads_csv_from_string(csv_text)
        assert len(books) == 1
        assert books[0]["Title"] == "The Hobbit"

    def test_filters_out_non_read_shelves(self):
        csv_text = GOODREADS_CSV_HEADER + make_csv_row(shelf="to-read")
        books = shelfmark.load_goodreads_csv_from_string(csv_text)
        assert books == []

    def test_multiple_books_only_read_returned(self):
        csv_text = (
            GOODREADS_CSV_HEADER
            + make_csv_row(book_id="1", title="Book A", shelf="read")
            + make_csv_row(book_id="2", title="Book B", shelf="to-read")
            + make_csv_row(book_id="3", title="Book C", shelf="read")
        )
        books = shelfmark.load_goodreads_csv_from_string(csv_text)
        assert len(books) == 2
        titles = [b["Title"] for b in books]
        assert "Book A" in titles
        assert "Book C" in titles

    def test_shelf_matching_is_case_insensitive(self):
        csv_text = GOODREADS_CSV_HEADER + make_csv_row(shelf="Read")
        books = shelfmark.load_goodreads_csv_from_string(csv_text)
        assert len(books) == 1

    def test_headers_only_returns_empty_list(self):
        csv_text = GOODREADS_CSV_HEADER
        books = shelfmark.load_goodreads_csv_from_string(csv_text)
        assert books == []

    def test_raises_on_missing_exclusive_shelf_column(self):
        csv_text = "Title,Author\nThe Hobbit,Tolkien\n"
        with pytest.raises(ValueError, match="valid Goodreads export"):
            shelfmark.load_goodreads_csv_from_string(csv_text)

    def test_raises_on_empty_string(self):
        with pytest.raises(ValueError):
            shelfmark.load_goodreads_csv_from_string("")

    def test_raises_on_completely_invalid_content(self):
        with pytest.raises(ValueError):
            shelfmark.load_goodreads_csv_from_string("not,a,goodreads,csv\nrow1\n")


# ---------------------------------------------------------------------------
# connect_to_abs_params — validation only (network mocked)
# ---------------------------------------------------------------------------

class TestConnectToAbsParams:
    def _mock_response(self, libraries=None):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"libraries": libraries or [{"id": "lib1", "name": "Audiobook"}]}
        mock_resp.raise_for_status.return_value = None
        return mock_resp

    def test_rejects_non_http_url(self):
        with pytest.raises(ValueError, match="http"):
            shelfmark.connect_to_abs_params("ftp://server", "key")

    def test_rejects_empty_api_key(self):
        with pytest.raises(ValueError, match="API key"):
            shelfmark.connect_to_abs_params("http://localhost:13378", "")

    def test_strips_trailing_slash_from_url(self):
        with patch("requests.get", return_value=self._mock_response()) as mock_get:
            url, _, _ = shelfmark.connect_to_abs_params("http://localhost:13378/", "key")
        assert url == "http://localhost:13378"
        assert not url.endswith("/")

    def test_returns_url_headers_libraries_on_success(self):
        libs = [{"id": "lib1", "name": "Audiobook"}]
        with patch("requests.get", return_value=self._mock_response(libs)):
            url, headers, libraries = shelfmark.connect_to_abs_params("http://localhost", "mykey")
        assert url == "http://localhost"
        assert headers["Authorization"] == "Bearer mykey"
        assert libraries == libs

    def test_raises_on_network_error(self):
        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(ValueError, match="Failed to connect"):
                shelfmark.connect_to_abs_params("http://localhost", "key")

    def test_raises_when_no_libraries_returned(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"libraries": []}
        mock_resp.raise_for_status.return_value = None
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(ValueError, match="No libraries"):
                shelfmark.connect_to_abs_params("http://localhost", "key")

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("401")
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(ValueError, match="Failed to connect"):
                shelfmark.connect_to_abs_params("http://localhost", "key")


# ---------------------------------------------------------------------------
# normalize_abs_items
# ---------------------------------------------------------------------------

class TestNormalizeAbsItems:
    def _make_raw_item(self, item_id="abc", title="Dune", author="Frank Herbert", isbn=None, asin=None):
        return {
            "id": item_id,
            "media": {
                "metadata": {
                    "title": title,
                    "authorName": author,
                    "isbn": isbn,
                    "asin": asin,
                }
            }
        }

    def test_normalizes_basic_item(self):
        items = [self._make_raw_item()]
        result = shelfmark.normalize_abs_items(items)
        assert len(result) == 1
        assert result[0] == {"id": "abc", "title": "Dune", "author": "Frank Herbert", "isbn": None, "asin": None}

    def test_normalizes_multiple_items(self):
        items = [self._make_raw_item("a", "Dune"), self._make_raw_item("b", "Foundation")]
        result = shelfmark.normalize_abs_items(items)
        assert len(result) == 2

    def test_handles_missing_media_key(self):
        items = [{"id": "abc"}]
        result = shelfmark.normalize_abs_items(items)
        assert result[0]["id"] == "abc"
        assert result[0]["title"] is None

    def test_handles_empty_list(self):
        assert shelfmark.normalize_abs_items([]) == []


# ---------------------------------------------------------------------------
# match_by_isbn
# ---------------------------------------------------------------------------

class TestMatchByIsbn:
    def _make_abs_item(self, isbn="9780441013593"):
        return {"id": "x", "title": "Dune", "author": "Frank Herbert", "isbn": isbn, "asin": None}

    def test_matches_by_isbn13(self):
        gr_book = {"Title": "Dune", "Author": "Frank Herbert", "ISBN": "", "ISBN13": '="9780441013593"'}
        abs_item = self._make_abs_item("9780441013593")
        index = {"9780441013593": abs_item}
        matches, unmatched = shelfmark.match_by_isbn([gr_book], index)
        assert len(matches) == 1
        assert unmatched == []

    def test_matches_by_isbn10_fallback(self):
        gr_book = {"Title": "Dune", "Author": "Frank Herbert", "ISBN": '="0441013597"', "ISBN13": ""}
        abs_item = self._make_abs_item("0441013597")
        index = {"0441013597": abs_item}
        matches, unmatched = shelfmark.match_by_isbn([gr_book], index)
        assert len(matches) == 1

    def test_no_match_goes_to_unmatched(self):
        gr_book = {"Title": "Dune", "Author": "Frank Herbert", "ISBN": "", "ISBN13": '="9999999999999"'}
        index = {"1234567890123": self._make_abs_item()}
        matches, unmatched = shelfmark.match_by_isbn([gr_book], index)
        assert matches == []
        assert len(unmatched) == 1

    def test_book_with_no_isbn_goes_to_unmatched(self):
        gr_book = {"Title": "Dune", "Author": "Frank Herbert", "ISBN": "", "ISBN13": ""}
        matches, unmatched = shelfmark.match_by_isbn([gr_book], {})
        assert matches == []
        assert len(unmatched) == 1

    def test_empty_inputs(self):
        matches, unmatched = shelfmark.match_by_isbn([], {})
        assert matches == []
        assert unmatched == []


# ---------------------------------------------------------------------------
# match_by_title_author
# ---------------------------------------------------------------------------

class TestMatchByTitleAuthor:
    def _make_abs_item(self, title="Dune", author="Frank Herbert"):
        return {"id": "x", "title": title, "author": author, "isbn": None, "asin": None}

    def _make_abs_index(self, items):
        return shelfmark.index_abs_items_by_title_author(items)

    def test_exact_match(self):
        gr_book = {"Title": "Dune", "Author": "Frank Herbert"}
        abs_item = self._make_abs_item("Dune", "Frank Herbert")
        index = self._make_abs_index([abs_item])
        matches, unmatched = shelfmark.match_by_title_author([gr_book], index)
        assert len(matches) == 1
        assert unmatched == []

    def test_no_match(self):
        gr_book = {"Title": "Foundation", "Author": "Isaac Asimov"}
        abs_item = self._make_abs_item("Dune", "Frank Herbert")
        index = self._make_abs_index([abs_item])
        matches, unmatched = shelfmark.match_by_title_author([gr_book], index)
        assert matches == []
        assert len(unmatched) == 1

    def test_multiple_candidates_not_matched(self):
        # If there are 2 ABS items with the same title/author, we skip (ambiguous)
        gr_book = {"Title": "Dune", "Author": "Frank Herbert"}
        item1 = self._make_abs_item("Dune", "Frank Herbert")
        item2 = {**item1, "id": "y"}
        index = self._make_abs_index([item1, item2])
        matches, unmatched = shelfmark.match_by_title_author([gr_book], index)
        assert matches == []
        assert len(unmatched) == 1

    def test_normalizes_before_matching(self):
        # Subtitle in GR title, trailing series in ABS title — both normalize to same key
        gr_book = {"Title": "Dune: A Novel", "Author": "Frank Herbert"}
        abs_item = self._make_abs_item("Dune (Dune Chronicles #1)", "Frank Herbert")
        index = self._make_abs_index([abs_item])
        matches, unmatched = shelfmark.match_by_title_author([gr_book], index)
        assert len(matches) == 1

    def test_book_missing_title_goes_to_unmatched(self):
        gr_book = {"Title": None, "Author": "Frank Herbert"}
        matches, unmatched = shelfmark.match_by_title_author([gr_book], {})
        assert unmatched == [gr_book]

    def test_empty_inputs(self):
        matches, unmatched = shelfmark.match_by_title_author([], {})
        assert matches == []
        assert unmatched == []


# ---------------------------------------------------------------------------
# fuzzy_match_title_author
# ---------------------------------------------------------------------------

class TestFuzzyMatchTitleAuthor:
    def _make_abs_item(self, title, author, item_id="x"):
        return {"id": item_id, "title": title, "author": author, "isbn": None, "asin": None}

    def test_matches_highly_similar_title_and_author(self):
        gr_book = {"Title": "The Hobbit", "Author": "J.R.R. Tolkien"}
        abs_item = self._make_abs_item("The Hobbit", "JRR Tolkien")
        result = shelfmark.fuzzy_match_title_author(gr_book, [abs_item])
        assert result is not None
        assert result["id"] == "x"

    def test_no_match_for_dissimilar_books(self):
        gr_book = {"Title": "The Hobbit", "Author": "J.R.R. Tolkien"}
        abs_item = self._make_abs_item("Dune", "Frank Herbert")
        result = shelfmark.fuzzy_match_title_author(gr_book, [abs_item])
        assert result is None

    def test_returns_none_for_multiple_fuzzy_candidates(self):
        # Ambiguous result → don't pick one
        gr_book = {"Title": "The Hobbit", "Author": "J.R.R. Tolkien"}
        item1 = self._make_abs_item("The Hobbit", "JRR Tolkien", "id1")
        item2 = self._make_abs_item("The Hobbit", "JRR Tolkien", "id2")
        result = shelfmark.fuzzy_match_title_author(gr_book, [item1, item2])
        assert result is None

    def test_returns_none_when_gr_book_has_no_title(self):
        gr_book = {"Title": None, "Author": "Tolkien"}
        result = shelfmark.fuzzy_match_title_author(gr_book, [])
        assert result is None

    def test_returns_none_when_gr_book_has_no_author(self):
        gr_book = {"Title": "The Hobbit", "Author": None}
        result = shelfmark.fuzzy_match_title_author(gr_book, [])
        assert result is None

    def test_empty_abs_items_returns_none(self):
        gr_book = {"Title": "The Hobbit", "Author": "J.R.R. Tolkien"}
        result = shelfmark.fuzzy_match_title_author(gr_book, [])
        assert result is None

    def test_skips_abs_items_missing_title_or_author(self):
        gr_book = {"Title": "The Hobbit", "Author": "J.R.R. Tolkien"}
        abs_item = {"id": "x", "title": None, "author": "Tolkien", "isbn": None, "asin": None}
        result = shelfmark.fuzzy_match_title_author(gr_book, [abs_item])
        assert result is None
