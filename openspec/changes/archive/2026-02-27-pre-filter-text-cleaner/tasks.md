## 1. Core Module

- [x] 1.1 Create `pipeline/core/text_cleaner.py` with `CleanStats` dataclass and `clean_transcript()` main function
- [x] 1.2 Implement `_remove_header_footer_repeats()` — lines ≥3 occurrences AND <100 chars
- [x] 1.3 Implement `_remove_toc()` — dot-leader regex + TOC heading patterns (Vietnamese + English)
- [x] 1.4 Implement `_remove_blank_pages()` — split by page break markers, remove segments <50 chars
- [x] 1.5 Implement `_remove_page_numbers()` — bare digits, dash-wrapped, Page/Trang prefix, X/Y pagination
- [x] 1.6 Implement `_remove_watermarks()` — lines >5 occurrences AND <80 chars
- [x] 1.7 Implement `_merge_blank_lines()` — consecutive blanks → single blank
- [x] 1.8 Implement `_normalize_whitespace()` — tabs→spaces, trailing strip, preserve Vietnamese diacritics
- [x] 1.9 Implement `format_clean_summary()` utility for logging

## 2. Integration

- [x] 2.1 Add `clean_input: bool = True` field to `BuildConfig` in `pipeline/core/types.py`
- [x] 2.2 Read `clean_input` from YAML config in `pipeline/core/config.py`
- [x] 2.3 Integrate cleaner into `read_transcript()` in `pipeline/core/utils.py`
- [x] 2.4 Integrate cleaner into `read_all_transcripts()` in `pipeline/core/utils.py` — add clean stats to result dict

## 3. Tests

- [x] 3.1 Create `pipeline/tests/test_text_cleaner.py` with tests for empty/disabled/idempotent cases
- [x] 3.2 Add tests for header/footer removal (repeated short lines, keep long lines)
- [x] 3.3 Add tests for TOC removal (dot leaders, Vietnamese patterns, preserve normal dots)
- [x] 3.4 Add tests for page number removal (bare numbers, dash-wrapped, Page/Trang, preserve content lines)
- [x] 3.5 Add tests for watermark removal, blank line merging, whitespace normalization
- [x] 3.6 Add tests for Vietnamese diacritics preservation and format_clean_summary
- [x] 3.7 Add real-world PDF integration test with mixed noise + Vietnamese content
- [x] 3.8 Run full test suite: `cd pipeline && python -m pytest tests/ -x -v` — all tests MUST pass
