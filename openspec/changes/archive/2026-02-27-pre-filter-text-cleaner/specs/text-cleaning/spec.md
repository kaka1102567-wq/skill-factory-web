## ADDED Requirements

### Requirement: Clean transcript removes repeated header/footer lines
The system SHALL remove lines that appear ≥3 times AND are shorter than 100 characters from transcript text. Empty lines and lines shorter than 2 characters SHALL be excluded from frequency counting.

#### Scenario: Copyright line repeated across pages
- **WHEN** transcript contains "© 2024 Company" appearing 5 times among content lines
- **THEN** all instances of "© 2024 Company" are removed and content lines are preserved

#### Scenario: Long repeated line preserved
- **WHEN** a line of 120+ characters appears 3 times
- **THEN** the line is kept (likely real content, not header/footer)

### Requirement: Clean transcript removes TOC entries with dot leaders
The system SHALL remove lines matching dot-leader patterns (3+ consecutive dots followed by a number) and standalone TOC heading lines ("Table of Contents", "Mục lục", "Nội dung").

#### Scenario: Vietnamese TOC with dot leaders
- **WHEN** transcript contains "Chương 1: Giới thiệu .......... 3"
- **THEN** the TOC entry line is removed

#### Scenario: Chapter heading without dots preserved
- **WHEN** transcript contains "Chương 1: Giới thiệu" (no dot leaders)
- **THEN** the line is preserved as content

#### Scenario: Normal sentences with periods preserved
- **WHEN** transcript contains "This is a sentence. Another sentence."
- **THEN** the line is preserved (periods are not dot leaders)

### Requirement: Clean transcript removes near-blank page segments
The system SHALL split text by page break markers (form feed `\x0c`, `---`, `===`) and remove segments with fewer than 50 characters of content after stripping whitespace. If no page break markers exist, this step SHALL be skipped.

#### Scenario: Form feed with blank page
- **WHEN** transcript contains a form feed character followed by only whitespace and a page number
- **THEN** that page segment is removed

### Requirement: Clean transcript removes standalone page numbers
The system SHALL remove lines that contain ONLY page number patterns: bare digits (1-4 digits), dash-wrapped numbers ("— 42 —"), "Page X" / "Trang X" prefixes, or "X / Y" pagination. Lines with additional content after the number SHALL NOT be removed.

#### Scenario: Bare number line removed
- **WHEN** a line contains only "42"
- **THEN** the line is removed

#### Scenario: Number with content preserved
- **WHEN** a line contains "42 ways to succeed"
- **THEN** the line is preserved

#### Scenario: Vietnamese page prefix
- **WHEN** a line contains only "Trang 12"
- **THEN** the line is removed

### Requirement: Clean transcript removes watermark lines
The system SHALL remove non-empty lines shorter than 80 characters that appear more than 5 times in the transcript. This threshold is higher than header/footer detection to avoid false positives.

#### Scenario: DRAFT watermark repeated 8 times
- **WHEN** transcript contains "DRAFT" appearing 8 times
- **THEN** all "DRAFT" lines are removed

### Requirement: Clean transcript merges consecutive blank lines
The system SHALL merge 2 or more consecutive blank/whitespace-only lines into a single blank line. Single blank lines (paragraph separators) SHALL be preserved.

#### Scenario: Five blank lines between paragraphs
- **WHEN** 5 consecutive blank lines appear between content
- **THEN** they are merged into 1 blank line

### Requirement: Clean transcript normalizes whitespace
The system SHALL convert tabs to 4 spaces and strip trailing whitespace from lines. Leading whitespace (indentation) SHALL be preserved. Vietnamese diacritics (ă, â, đ, ê, ô, ơ, ư) and all non-whitespace characters SHALL never be modified.

#### Scenario: Tab normalization
- **WHEN** line contains "Content\twith\ttabs"
- **THEN** tabs are replaced with 4 spaces

#### Scenario: Vietnamese diacritics preserved
- **WHEN** line contains "Đây là nội dung tiếng Việt có dấu: ă â đ ê ô ơ ư"
- **THEN** all characters are preserved exactly

### Requirement: Cleaning is idempotent
Applying `clean_transcript` to already-cleaned text SHALL produce identical output. `clean(clean(text)) == clean(text)` MUST hold for all inputs.

#### Scenario: Double clean produces same result
- **WHEN** raw text is cleaned once producing `result1`, then `result1` is cleaned again producing `result2`
- **THEN** `result1 == result2`

### Requirement: Cleaning is configurable
The system SHALL support disabling cleaning via `BuildConfig.clean_input` field (default `True`) and `clean_transcript(text, enabled=False)` parameter. When disabled, text SHALL be returned unchanged.

#### Scenario: Disabled via parameter
- **WHEN** `clean_transcript(text, enabled=False)` is called
- **THEN** original text is returned with empty `steps_applied`

### Requirement: Cleaning returns statistics
`clean_transcript` SHALL return a `CleanStats` dataclass with: `original_lines`, `cleaned_lines`, `removed_lines`, `original_chars`, `cleaned_chars`, `steps_applied` (list of step names that made changes).

#### Scenario: Stats reflect cleaning actions
- **WHEN** cleaning removes header/footer and page numbers
- **THEN** `stats.steps_applied` contains `["header_footer", "page_numbers"]` and `stats.removed_lines > 0`

### Requirement: Transparent integration via utils.py
Cleaning SHALL be integrated into `read_transcript()` and `read_all_transcripts()` in `pipeline/core/utils.py`. All pipeline phases consuming transcript content SHALL receive cleaned text without code changes.

#### Scenario: Phase reads cleaned content
- **WHEN** any phase calls `read_all_transcripts(config.transcript_paths)`
- **THEN** returned content is pre-cleaned (if `clean_input` is enabled)
