"""Tests for JinaClient — all mocked, no real API calls."""

import httpx
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from pipeline.clients.jina_client import (
    JinaClient, _parse_search_results,
    JINA_READER_BASE, JINA_SEARCH_BASE,
    FREE_MIN_INTERVAL, PAID_MIN_INTERVAL,
)


# ── Init ──

def test_init_free_tier():
    c = JinaClient()
    assert c.min_interval >= 0.5
    c.close()


def test_init_with_api_key():
    c = JinaClient(api_key="test-key")
    assert c.min_interval < 0.5
    c.close()


# ── Fetch ──

def test_fetch_success():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "# Title\n\nLong content here that is more than fifty characters for sure."
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    result = c.fetch("https://example.com")
    assert result is not None
    assert "Title" in result
    c._client.get.assert_called_once()


def test_fetch_empty_returns_none():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "short"
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    assert c.fetch("https://example.com") is None


def test_fetch_404_returns_none():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    assert c.fetch("https://example.com") is None


def test_fetch_timeout_retries():
    c = JinaClient(max_retries=1)
    c._client = MagicMock()
    c._client.get.side_effect = httpx.TimeoutException("timeout")

    result = c.fetch("https://example.com")
    assert result is None
    assert c._client.get.call_count == 2  # initial + 1 retry


def test_fetch_target_selector_header():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "x" * 100
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    c.fetch("https://example.com", target_selector=".main-content")
    call_kwargs = c._client.get.call_args
    assert call_kwargs[1]["headers"]["X-Target-Selector"] == ".main-content"


# ── Search ──

SEARCH_RESPONSE = (
    "Title: Getting Started\n"
    "URL Source: https://example.com\n"
    "Markdown Content:\n"
    "# Getting Started\nContent here.\n"
    "\n"
    "Title: API Ref\n"
    "URL Source: https://example.com/api\n"
    "Markdown Content:\n"
    "# API\nDocs here."
)


def test_search_success():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SEARCH_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    results = c.search("example docs")
    assert len(results) == 2
    assert results[0]["title"] == "Getting Started"
    assert results[1]["url"] == "https://example.com/api"


def test_search_empty_returns_list():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = ""
    mock_resp.raise_for_status = MagicMock()
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    assert c.search("nothing") == []


def test_search_network_error():
    c = JinaClient()
    c._client = MagicMock()
    c._client.get.side_effect = httpx.ConnectError("fail")

    assert c.search("test") == []


def test_search_max_results():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SEARCH_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    results = c.search("test", max_results=1)
    assert len(results) == 1


# ── Parse ──

def test_parse_search_results_basic():
    results = _parse_search_results(SEARCH_RESPONSE)
    assert len(results) == 2
    assert results[0]["url"] == "https://example.com"
    assert "Content here" in results[0]["snippet"]


def test_parse_search_results_empty():
    assert _parse_search_results("") == []


def test_parse_search_results_no_url():
    text = "Title: NoURL\nSome random text"
    assert _parse_search_results(text) == []


# ── URL construction ──

def test_fetch_url_construction():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "x" * 100
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    c.fetch("https://example.com/page")
    url_arg = c._client.get.call_args[0][0]
    assert url_arg == JINA_READER_BASE + "https://example.com/page"


def test_search_url_construction():
    c = JinaClient()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = ""
    mock_resp.raise_for_status = MagicMock()
    c._client = MagicMock()
    c._client.get.return_value = mock_resp

    c.search("hello world")
    url_arg = c._client.get.call_args[0][0]
    assert url_arg == JINA_SEARCH_BASE + "hello+world"
