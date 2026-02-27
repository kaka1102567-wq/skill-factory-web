## Context

Pipeline đọc transcript qua `utils.py` → `read_transcript()` (single file → string) và `read_all_transcripts()` (multi file → list[dict]). Mọi phases (P1-P6) dùng content từ 2 hàm này. Config (`BuildConfig`) chỉ lưu paths, không lưu content.

Current flow: `config.py` discover paths → phases gọi `read_all_transcripts(config.transcript_paths)` → raw content vào LLM.

## Goals / Non-Goals

**Goals:**
- Clean transcript text trước khi phases xử lý (transparent integration)
- Giảm 15-30% noise tokens → giảm API cost + tăng extract quality
- Idempotent: `clean(clean(text)) == clean(text)`
- Configurable on/off via `BuildConfig.clean_input`

**Non-Goals:**
- Không sửa pipeline phases (P1-P6) — chỉ touch utils.py integration point
- Không làm advanced NLP/ML-based cleaning
- Không normalize content semantics (e.g., synonym resolution)

## Decisions

### D1: Integration point — `utils.py` thay vì `config.py`
**Choice**: Tích hợp vào `read_transcript()` / `read_all_transcripts()` trong `utils.py`.
**Rationale**: Config.py chỉ discover paths, không đọc content. Utils.py là nơi content được đọc lần đầu → clean tại đây = transparent cho tất cả consumers.
**Alternative**: Tạo hàm wrapper riêng — rejected vì mỗi phase phải gọi manual, dễ quên.

### D2: Clean stats reporting — return stats, không log trực tiếp
**Choice**: `clean_transcript()` return `(text, CleanStats)`. Caller quyết định có log hay không.
**Rationale**: `text_cleaner.py` là pure utility, không nên depend on PipelineLogger. `read_all_transcripts()` trong utils.py sẽ collect stats vào dict result.
**Alternative**: Inject logger — rejected vì over-coupling cho 1 utility module.

### D3: Step order cố định, không configurable
**Choice**: 7 steps chạy theo thứ tự cố định: header/footer → TOC → blank pages → page numbers → watermarks → merge blanks → normalize whitespace.
**Rationale**: Order matters (header/footer trước để watermark threshold chính xác hơn; normalize cuối để không ảnh hưởng pattern matching). Configurable per-step là YAGNI.

### D4: Conservative regex — giữ content khi nghi ngờ
**Choice**: False negatives (miss noise) tốt hơn false positives (xóa content).
**Rationale**: Content bị xóa nhầm → mất knowledge atoms không recover được. Noise còn sót → chỉ tốn thêm tokens, phases vẫn hoạt động.

## Risks / Trade-offs

- **[False positive removal]** → Mitigation: conservative thresholds (header ≥3 repeats, watermark >5 repeats), page number regex anchored to line boundaries, test kỹ với Vietnamese text
- **[Performance với file lớn]** → Mitigation: All operations O(n) trên lines, không regex backtracking. File PDF typical < 100K lines → negligible
- **[Idempotency edge cases]** → Mitigation: Dedicated test `test_idempotent` verify clean(clean(x)) == clean(x)
