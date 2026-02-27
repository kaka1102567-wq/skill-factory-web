"""
Text cleaner — pre-filter OCR/PDF noise before pipeline processing.

Removes: header/footer repeats, TOC, blank pages, page numbers,
watermarks, excessive blank lines. Preserves meaningful content
including Vietnamese with diacritics.
"""

import re
from dataclasses import dataclass


@dataclass
class CleanStats:
    """Statistics about what was cleaned."""
    original_lines: int
    cleaned_lines: int
    removed_lines: int
    original_chars: int
    cleaned_chars: int
    steps_applied: list[str]


def clean_transcript(text: str, enabled: bool = True) -> tuple[str, CleanStats]:
    """
    Clean transcript text by removing OCR/PDF noise.
    Returns (cleaned_text, stats).
    Idempotent: clean(clean(text)) == clean(text).
    """
    if not enabled or not text or not text.strip():
        stats = CleanStats(
            original_lines=len(text.splitlines()) if text else 0,
            cleaned_lines=len(text.splitlines()) if text else 0,
            removed_lines=0,
            original_chars=len(text) if text else 0,
            cleaned_chars=len(text) if text else 0,
            steps_applied=[],
        )
        return text, stats

    original_lines = text.splitlines()
    original_chars = len(text)
    steps = []
    lines = list(original_lines)

    for step_fn, step_name in [
        (_remove_header_footer_repeats, "header_footer"),
        (_remove_toc, "toc"),
        (_remove_blank_pages, "blank_pages"),
        (_remove_page_numbers, "page_numbers"),
        (_remove_watermarks, "watermarks"),
        (_merge_blank_lines, "merge_blanks"),
        (_normalize_whitespace, "normalize_ws"),
    ]:
        lines, changed = step_fn(lines)
        if changed:
            steps.append(step_name)

    cleaned_text = "\n".join(lines).strip()

    stats = CleanStats(
        original_lines=len(original_lines),
        cleaned_lines=len(lines),
        removed_lines=len(original_lines) - len(lines),
        original_chars=original_chars,
        cleaned_chars=len(cleaned_text),
        steps_applied=steps,
    )
    return cleaned_text, stats


def _remove_header_footer_repeats(lines: list[str]) -> tuple[list[str], bool]:
    """Remove lines appearing >=3 times AND shorter than 100 chars."""
    freq: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if len(stripped) >= 2:
            freq[stripped] = freq.get(stripped, 0) + 1

    to_remove = {s for s, count in freq.items() if count >= 3 and len(s) < 100}
    if not to_remove:
        return lines, False

    result = [line for line in lines if line.strip() not in to_remove]
    return result, len(result) != len(lines)


# TOC heading patterns (standalone only)
_TOC_HEADINGS = re.compile(
    r'^(table\s+of\s+contents|mục\s+lục|nội\s+dung)$',
    re.IGNORECASE,
)
# Dot leader: text followed by 3+ dots then a page number
_DOT_LEADER = re.compile(r'^.+\.{3,}\s*\d+\s*$')


def _remove_toc(lines: list[str]) -> tuple[list[str], bool]:
    """Remove TOC headings and dot-leader lines. Keep chapter headings without dots."""
    result = []
    changed = False
    for line in lines:
        stripped = line.strip()
        if _TOC_HEADINGS.match(stripped) or _DOT_LEADER.match(stripped):
            changed = True
        else:
            result.append(line)
    return result, changed


def _remove_blank_pages(lines: list[str]) -> tuple[list[str], bool]:
    """Remove page segments with <50 chars after stripping. Requires \\x0c markers."""
    full_text = "\n".join(lines)
    if "\x0c" not in full_text:
        return lines, False

    segments = full_text.split("\x0c")
    kept = [seg for seg in segments if len(seg.strip()) >= 50]
    if len(kept) == len(segments):
        return lines, False

    rejoined = "\x0c".join(kept)
    return rejoined.splitlines(), True


_PAGE_NUM_PATTERNS = [
    re.compile(r'^\s*\d{1,4}\s*$'),                              # bare digits
    re.compile(r'^\s*[-\u2014]\s*\d{1,4}\s*[-\u2014]\s*$'),     # dash-wrapped
    re.compile(r'^\s*(page|trang)\s+\d+\s*$', re.IGNORECASE),   # Page/Trang prefix
    re.compile(r'^\s*\d+\s*/\s*\d+\s*$'),                       # X/Y pagination
]


def _remove_page_numbers(lines: list[str]) -> tuple[list[str], bool]:
    """Remove standalone page number lines. Anchored patterns prevent false matches."""
    result = []
    changed = False
    for line in lines:
        if any(p.match(line) for p in _PAGE_NUM_PATTERNS):
            changed = True
        else:
            result.append(line)
    return result, changed


def _remove_watermarks(lines: list[str]) -> tuple[list[str], bool]:
    """Remove lines appearing >5 times AND shorter than 80 chars."""
    freq: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if stripped:
            freq[stripped] = freq.get(stripped, 0) + 1

    to_remove = {s for s, count in freq.items() if count > 5 and len(s) < 80}
    if not to_remove:
        return lines, False

    result = [line for line in lines if line.strip() not in to_remove]
    return result, len(result) != len(lines)


def _merge_blank_lines(lines: list[str]) -> tuple[list[str], bool]:
    """Collapse consecutive blank/whitespace-only lines into a single blank line."""
    result = []
    changed = False
    prev_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            changed = True
            continue
        result.append(line)
        prev_blank = is_blank
    return result, changed


def _normalize_whitespace(lines: list[str]) -> tuple[list[str], bool]:
    """Tab -> 4 spaces. Strip trailing whitespace. Preserve leading whitespace."""
    result = []
    changed = False
    for line in lines:
        normalized = line.replace("\t", "    ").rstrip()
        if normalized != line:
            changed = True
        result.append(normalized)
    return result, changed


def format_clean_summary(stats: CleanStats) -> str:
    """Format CleanStats for logging. No side effects."""
    if not stats.steps_applied:
        return "Clean: no noise detected"

    char_saved = stats.original_chars - stats.cleaned_chars
    if stats.original_lines > 0:
        pct = (stats.removed_lines / stats.original_lines) * 100
    else:
        pct = 0.0

    steps_str = ", ".join(stats.steps_applied)
    return (
        f"Cleaned: removed {stats.removed_lines} lines "
        f"({pct:.1f}%), saved ~{char_saved} chars. Steps: {steps_str}"
    )
