"""Tests for the fetch-urls CLI command."""

import os
import pytest
from unittest.mock import MagicMock, patch

from pipeline.commands.fetch_urls import (
    _parse_urls,
    _extract_title,
    _html_to_markdown,
    _find_main_content,
    _remove_noise,
    fetch_and_convert,
    run_fetch_urls,
)
from bs4 import BeautifulSoup


# ── URL parsing ──

def test_parse_urls_comma_separated():
    result = _parse_urls("https://a.com,https://b.com")
    assert result == ["https://a.com", "https://b.com"]


def test_parse_urls_newline_separated():
    result = _parse_urls("https://a.com\nhttps://b.com\n")
    assert result == ["https://a.com", "https://b.com"]


def test_parse_urls_rejects_invalid():
    result = _parse_urls("ftp://bad.com,not-a-url,https://good.com")
    assert result == ["https://good.com"]


def test_parse_urls_empty_string():
    assert _parse_urls("") == []


# ── HTML extraction ──

SAMPLE_HTML = """
<html>
<head><title>Test Article</title></head>
<body>
<nav><a href="/">Home</a></nav>
<article>
  <h1>Main Heading</h1>
  <p>First paragraph with <strong>bold</strong> and <em>italic</em>.</p>
  <h2>Sub Heading</h2>
  <ul><li>Item 1</li><li>Item 2</li></ul>
  <pre><code>print("hello")</code></pre>
</article>
<footer>Footer text</footer>
</body>
</html>
"""


def test_extract_title():
    soup = BeautifulSoup(SAMPLE_HTML, 'lxml')
    assert _extract_title(soup) == "Test Article"


def test_remove_noise_strips_nav_footer():
    soup = BeautifulSoup(SAMPLE_HTML, 'lxml')
    _remove_noise(soup)
    assert soup.find('nav') is None
    assert soup.find('footer') is None


def test_find_main_content_prefers_article():
    soup = BeautifulSoup(SAMPLE_HTML, 'lxml')
    main = _find_main_content(soup)
    assert main.name == 'article'


def test_html_to_markdown_headings_and_text():
    soup = BeautifulSoup(SAMPLE_HTML, 'lxml')
    _remove_noise(soup)
    main = _find_main_content(soup)
    md = _html_to_markdown(main)
    assert "# Main Heading" in md
    assert "## Sub Heading" in md
    assert "**bold**" in md
    assert "*italic*" in md
    assert "- Item 1" in md
    assert '```' in md
    assert 'print("hello")' in md


# ── fetch_and_convert with mock ──

def test_fetch_and_convert_success():
    mock_client = MagicMock()
    mock_client.get.return_value = SAMPLE_HTML
    content, title = fetch_and_convert("https://example.com/article", mock_client)
    assert title == "Test Article"
    assert "Main Heading" in content
    assert content is not None


def test_fetch_and_convert_network_error():
    mock_client = MagicMock()
    mock_client.get.side_effect = Exception("Connection refused")
    content, title = fetch_and_convert("https://fail.com", mock_client)
    assert content is None
    assert title is None


# ── run_fetch_urls end-to-end ──

def test_run_fetch_urls_creates_files(tmp_path):
    output_dir = str(tmp_path / "output")

    with patch("pipeline.clients.web_client.WebClient") as MockClient:
        instance = MockClient.return_value
        instance.get.return_value = SAMPLE_HTML
        instance.close = MagicMock()

        code = run_fetch_urls("https://example.com/page", output_dir)

    assert code == 0
    files = os.listdir(output_dir)
    assert len(files) == 1
    assert files[0].startswith("url_001_")
    assert files[0].endswith(".md")

    content = open(os.path.join(output_dir, files[0]), encoding="utf-8").read()
    assert "source_url: https://example.com/page" in content
    assert "Main Heading" in content


def test_run_fetch_urls_no_valid_urls():
    code = run_fetch_urls("not-a-url", "/tmp/fake")
    assert code == 1
