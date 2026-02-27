"""Tests for pipeline/core/text_cleaner.py."""

import pytest
from pipeline.core.text_cleaner import (
    clean_transcript,
    format_clean_summary,
    CleanStats,
    _remove_header_footer_repeats,
    _remove_toc,
    _remove_page_numbers,
    _remove_watermarks,
    _merge_blank_lines,
    _normalize_whitespace,
)


# ── TestCleanTranscript ──────────────────────────────────

class TestCleanTranscript:
    def test_empty_string(self):
        result, stats = clean_transcript("")
        assert result == ""
        assert stats.removed_lines == 0
        assert stats.steps_applied == []

    def test_whitespace_only(self):
        result, stats = clean_transcript("   \n\n   ")
        assert stats.steps_applied == []

    def test_disabled_returns_unchanged(self):
        text = "Header\nHeader\nHeader\nContent line here."
        result, stats = clean_transcript(text, enabled=False)
        assert result == text
        assert stats.steps_applied == []
        assert stats.removed_lines == 0

    def test_idempotent(self):
        """clean(clean(text)) == clean(text)"""
        text = (
            "Company Footer\nCompany Footer\nCompany Footer\n"
            "Real content here that matters.\n"
            "Chapter 1..............................42\n"
            "\n\n\n"
            "More real content.\n"
            "\t Indented line.\n"
        )
        first, _ = clean_transcript(text)
        second, _ = clean_transcript(first)
        assert first == second


# ── TestHeaderFooterRepeats ──────────────────────────────

class TestHeaderFooterRepeats:
    def test_removes_lines_repeated_3_or_more_times(self):
        lines = [
            "Company Inc.",
            "Real content line one.",
            "Company Inc.",
            "Real content line two.",
            "Company Inc.",
            "Real content line three.",
        ]
        result, changed = _remove_header_footer_repeats(lines)
        assert changed is True
        assert "Company Inc." not in result
        assert "Real content line one." in result

    def test_keeps_long_repeated_lines(self):
        long_line = "A" * 100  # exactly 100 chars — boundary, should be kept
        lines = [long_line, "other", long_line, "other2", long_line]
        result, changed = _remove_header_footer_repeats(lines)
        assert long_line in result

    def test_keeps_lines_repeated_fewer_than_3_times(self):
        lines = ["Repeated line", "Content", "Repeated line", "More content"]
        result, changed = _remove_header_footer_repeats(lines)
        assert "Repeated line" in result

    def test_no_change_returns_false(self):
        lines = ["Unique line A", "Unique line B", "Unique line C"]
        _, changed = _remove_header_footer_repeats(lines)
        assert changed is False


# ── TestTOC ─────────────────────────────────────────────

class TestTOC:
    def test_removes_dot_leader_lines(self):
        lines = [
            "Introduction...............1",
            "Chapter 1..................5",
            "Normal sentence with some dots.",
        ]
        result, changed = _remove_toc(lines)
        assert changed is True
        assert "Introduction...............1" not in result
        assert "Chapter 1..................5" not in result
        assert "Normal sentence with some dots." in result

    def test_removes_english_toc_heading(self):
        lines = ["Table of Contents", "Some real content here."]
        result, changed = _remove_toc(lines)
        assert changed is True
        assert "Table of Contents" not in result
        assert "Some real content here." in result

    def test_removes_vietnamese_toc_heading(self):
        lines = ["Mục lục", "Nội dung", "Real Vietnamese content."]
        result, changed = _remove_toc(lines)
        assert changed is True
        assert "Mục lục" not in result
        assert "Nội dung" not in result

    def test_keeps_chapter_heading_without_dots(self):
        """Chapter headings without dot leaders must be preserved."""
        lines = ["Chương 1: Giới thiệu", "Real content below."]
        result, changed = _remove_toc(lines)
        assert "Chương 1: Giới thiệu" in result

    def test_keeps_normal_sentences_with_some_dots(self):
        lines = ["Dr. Smith went to the store.", "Version 1.2.3 is released."]
        result, _ = _remove_toc(lines)
        assert "Dr. Smith went to the store." in result
        assert "Version 1.2.3 is released." in result

    def test_no_change_returns_false(self):
        lines = ["Normal line", "Another normal line"]
        _, changed = _remove_toc(lines)
        assert changed is False


# ── TestPageNumbers ──────────────────────────────────────

class TestPageNumbers:
    def test_removes_bare_digits(self):
        lines = ["42", "Content here."]
        result, changed = _remove_page_numbers(lines)
        assert changed is True
        assert "42" not in result
        assert "Content here." in result

    def test_removes_dash_wrapped_numbers(self):
        lines = ["— 2 —", "- 10 -", "Content."]
        result, changed = _remove_page_numbers(lines)
        assert changed is True
        assert "— 2 —" not in result
        assert "- 10 -" not in result

    def test_removes_page_prefix(self):
        lines = ["Page 5", "Trang 10", "Content."]
        result, changed = _remove_page_numbers(lines)
        assert changed is True
        assert "Page 5" not in result
        assert "Trang 10" not in result

    def test_removes_x_of_y_pagination(self):
        lines = ["3/10", "Content line."]
        result, changed = _remove_page_numbers(lines)
        assert changed is True
        assert "3/10" not in result

    def test_keeps_numbers_in_content_lines(self):
        """Numbers embedded in sentences must not be removed."""
        lines = [
            "42 ways to succeed in business",
            "There are 10 steps to follow.",
            "Python 3/3.11 compatibility required.",
        ]
        result, changed = _remove_page_numbers(lines)
        assert "42 ways to succeed in business" in result
        assert "There are 10 steps to follow." in result

    def test_no_change_returns_false(self):
        lines = ["No page numbers here", "Just content"]
        _, changed = _remove_page_numbers(lines)
        assert changed is False


# ── TestWatermarks ───────────────────────────────────────

class TestWatermarks:
    def test_removes_lines_more_than_5_occurrences(self):
        watermark = "© 2024 Company"
        lines = [watermark] * 6 + ["Real content."]
        result, changed = _remove_watermarks(lines)
        assert changed is True
        assert watermark not in result
        assert "Real content." in result

    def test_keeps_lines_with_5_or_fewer_occurrences(self):
        line = "Short repeat"
        lines = [line] * 5 + ["Content."]
        result, changed = _remove_watermarks(lines)
        assert line in result

    def test_keeps_long_repeated_lines(self):
        long_watermark = "W" * 80  # exactly 80 chars — boundary, kept
        lines = [long_watermark] * 10 + ["Content."]
        result, _ = _remove_watermarks(lines)
        assert long_watermark in result


# ── TestMergeBlankLines ──────────────────────────────────

class TestMergeBlankLines:
    def test_collapses_multiple_blanks_to_one(self):
        lines = ["Content A", "", "", "", "", "", "Content B"]
        result, changed = _merge_blank_lines(lines)
        assert changed is True
        assert result.count("") == 1
        assert "Content A" in result
        assert "Content B" in result

    def test_preserves_single_blank_lines(self):
        lines = ["Content A", "", "Content B"]
        result, changed = _merge_blank_lines(lines)
        assert changed is False
        assert result == lines

    def test_no_change_returns_false(self):
        lines = ["A", "B", "C"]
        _, changed = _merge_blank_lines(lines)
        assert changed is False


# ── TestNormalizeWhitespace ──────────────────────────────

class TestNormalizeWhitespace:
    def test_tabs_to_spaces(self):
        lines = ["\tIndented content"]
        result, changed = _normalize_whitespace(lines)
        assert changed is True
        assert result[0] == "    Indented content"

    def test_strips_trailing_whitespace(self):
        lines = ["Content with trailing spaces   "]
        result, changed = _normalize_whitespace(lines)
        assert changed is True
        assert result[0] == "Content with trailing spaces"

    def test_preserves_leading_whitespace(self):
        lines = ["    Leading spaces preserved"]
        result, changed = _normalize_whitespace(lines)
        assert result[0] == "    Leading spaces preserved"

    def test_preserves_vietnamese_diacritics(self):
        """Vietnamese characters must survive normalization unchanged."""
        text = "ă â đ ê ô ơ ư Ắ Ầ Đ Ê Ô Ợ Ừ"
        lines = [text]
        result, _ = _normalize_whitespace(lines)
        assert result[0] == text

    def test_no_change_returns_false(self):
        lines = ["Clean line already"]
        _, changed = _normalize_whitespace(lines)
        assert changed is False


# ── TestFormatSummary ────────────────────────────────────

class TestFormatSummary:
    def test_no_changes_message(self):
        stats = CleanStats(
            original_lines=10, cleaned_lines=10, removed_lines=0,
            original_chars=200, cleaned_chars=200, steps_applied=[],
        )
        msg = format_clean_summary(stats)
        assert msg == "Clean: no noise detected"

    def test_with_changes_message(self):
        stats = CleanStats(
            original_lines=100, cleaned_lines=80, removed_lines=20,
            original_chars=5000, cleaned_chars=4000, steps_applied=["header_footer", "page_numbers"],
        )
        msg = format_clean_summary(stats)
        assert "20" in msg          # removed_lines count
        assert "20.0%" in msg       # percentage
        assert "1000" in msg        # chars saved
        assert "header_footer" in msg
        assert "page_numbers" in msg


# ── TestRealWorldPDF ─────────────────────────────────────

class TestRealWorldPDF:
    """Integration test with realistic PDF OCR output."""

    PDF_CONTENT = """\
AI Agent trong Thực Tiễn
Tài liệu khóa học

© 2024 AI Research Corp
© 2024 AI Research Corp
© 2024 AI Research Corp
© 2024 AI Research Corp
© 2024 AI Research Corp
© 2024 AI Research Corp

Mục lục
Chương 1: Giới thiệu...............1
Chương 2: Ứng dụng.................5
Chương 3: Tương lai.................10

1

Chương 1: Giới thiệu

AI Agent là một hệ thống tự động có khả năng nhận thức và hành động.
Đặc điểm chính bao gồm tự chủ, thích nghi và học hỏi liên tục.

— 2 —

Ứng dụng của AI Agent rất đa dạng trong nhiều lĩnh vực khác nhau.
Từ y tế đến giáo dục, AI đang thay đổi cách chúng ta làm việc.



3

Kết luận và hướng phát triển tiếp theo của công nghệ AI Agent.
"""

    def test_preserves_meaningful_vietnamese_content(self):
        cleaned, stats = clean_transcript(self.PDF_CONTENT)
        assert "AI Agent là một hệ thống tự động" in cleaned
        assert "Đặc điểm chính bao gồm" in cleaned
        assert "Ứng dụng của AI Agent" in cleaned

    def test_preserves_chapter_heading(self):
        """Chapter heading without dot leader must be kept."""
        cleaned, _ = clean_transcript(self.PDF_CONTENT)
        assert "Chương 1: Giới thiệu" in cleaned

    def test_removes_watermark(self):
        cleaned, _ = clean_transcript(self.PDF_CONTENT)
        assert "© 2024 AI Research Corp" not in cleaned

    def test_removes_dot_leader_toc(self):
        cleaned, _ = clean_transcript(self.PDF_CONTENT)
        assert "Chương 1: Giới thiệu...............1" not in cleaned
        assert "Chương 2: Ứng dụng.................5" not in cleaned

    def test_removes_page_numbers(self):
        cleaned, _ = clean_transcript(self.PDF_CONTENT)
        # Bare "1" or "3" standalone lines should be removed
        for line in cleaned.splitlines():
            stripped = line.strip()
            # No standalone digit-only lines
            assert not (stripped.isdigit() and len(stripped) <= 4), \
                f"Found standalone page number: {stripped!r}"

    def test_removes_dash_wrapped_page_numbers(self):
        cleaned, _ = clean_transcript(self.PDF_CONTENT)
        assert "— 2 —" not in cleaned

    def test_collapses_multiple_blank_lines(self):
        cleaned, _ = clean_transcript(self.PDF_CONTENT)
        lines = cleaned.splitlines()
        # No three consecutive blank lines
        for i in range(len(lines) - 2):
            triple_blank = (
                not lines[i].strip() and
                not lines[i + 1].strip() and
                not lines[i + 2].strip()
            )
            assert not triple_blank, f"Found 3+ consecutive blank lines at position {i}"

    def test_stats_reflect_cleaning(self):
        _, stats = clean_transcript(self.PDF_CONTENT)
        assert stats.removed_lines > 0
        assert len(stats.steps_applied) > 0
        assert stats.cleaned_chars < stats.original_chars
