## Phase Implementation Report

### Executed Phase
- Phase: pre-filter-text-cleaner
- Plan: none (direct task)
- Status: completed

### Files Modified
- `pipeline/core/text_cleaner.py` — NEW, 170 lines. CleanStats dataclass, clean_transcript(), 7 step functions, format_clean_summary()
- `pipeline/core/types.py` — +2 lines. Added `clean_input: bool = True` to BuildConfig after skip_optimize
- `pipeline/core/config.py` — +1 line. Added `clean_input=raw.get('clean_input', True)` to load_config() return
- `pipeline/core/utils.py` — +20 lines. read_transcript() and read_all_transcripts() now accept `clean` param; clean_stats added to result dict
- `pipeline/tests/test_text_cleaner.py` — NEW, 252 lines. 41 tests across 8 test classes
- `openspec/changes/pre-filter-text-cleaner/tasks.md` — all tasks marked [x]

### Tasks Completed
- [x] 1.1 text_cleaner.py with CleanStats + clean_transcript()
- [x] 1.2 _remove_header_footer_repeats() — ≥3 occurrences AND <100 chars
- [x] 1.3 _remove_toc() — dot-leader regex + TOC headings (EN + VI)
- [x] 1.4 _remove_blank_pages() — \x0c split, remove segments <50 chars
- [x] 1.5 _remove_page_numbers() — 4 anchored patterns
- [x] 1.6 _remove_watermarks() — >5 occurrences AND <80 chars
- [x] 1.7 _merge_blank_lines() — consecutive blanks → single blank
- [x] 1.8 _normalize_whitespace() — tabs→spaces, rstrip, preserve Vietnamese
- [x] 1.9 format_clean_summary() for logging
- [x] 2.1 BuildConfig.clean_input field
- [x] 2.2 load_config() reads clean_input from YAML
- [x] 2.3 read_transcript() integrates cleaner
- [x] 2.4 read_all_transcripts() adds clean_stats to result dict
- [x] 3.1–3.8 Test suite: 41 tests, all pass

### Tests Status
- New tests: 41/41 pass (0.15s)
- Full suite (excl. pre-existing env failures): 264 pass
- Pre-existing failures (unrelated to this task):
  - test_extract_pdf.py — `fitz` (PyMuPDF) not in venv
  - test_phases.py::TestClaudeClientMultiProvider — `openai` not in venv

### Issues Encountered
- Python not on PATH in bash shell; used `.claude/skills/.venv/Scripts/python.exe`
- Pre-existing test failures for missing `fitz` and `openai` packages in venv — not introduced by this work

### Next Steps
- None required. Module is idempotent, tested, integrated. Ready for use.
