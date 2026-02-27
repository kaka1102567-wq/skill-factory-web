## Why

Pipeline nhận text từ PDF/OCR/transcript chứa 15-30% noise (header/footer lặp, mục lục, page numbers, watermark, blank lines thừa). Noise tốn tokens LLM nhưng không mang giá trị → tăng chi phí API + giảm chất lượng extract. Cần pre-filter transparent trước khi phases xử lý.

## What Changes

- Thêm module `pipeline/core/text_cleaner.py` — 7 cleaning steps (header/footer, TOC, blank pages, page numbers, watermarks, merge blanks, normalize whitespace)
- Tích hợp cleaner vào `pipeline/core/utils.py` → `read_transcript()` và `read_all_transcripts()` tự động clean
- Thêm field `clean_input: bool = True` vào `BuildConfig` (types.py) + đọc từ YAML config (config.py)
- Thêm test file `pipeline/tests/test_text_cleaner.py`

## Capabilities

### New Capabilities
- `text-cleaning`: Pre-filter OCR/PDF noise từ transcript text trước pipeline processing. 7 idempotent cleaning steps, configurable on/off, preserves Vietnamese diacritics.

### Modified Capabilities
<!-- No existing spec requirements change — integration is additive only -->

## Impact

- **Code**: `pipeline/core/utils.py` (sửa 2 hàm), `pipeline/core/types.py` (thêm 1 field), `pipeline/core/config.py` (đọc config field)
- **APIs**: Không thay đổi API contract — transparent với tất cả phases
- **Dependencies**: Không thêm dependency mới (chỉ dùng `re`, `dataclasses` stdlib)
- **Risk**: False positive removal → constraint: khi nghi ngờ giữ content, regex conservative
