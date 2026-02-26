# Phase Implementation Report

## Executed Phase
- Phase: google-vision-ocr-integration
- Plan: none (direct task)
- Status: completed

## Files Modified

| File | Changes |
|------|---------|
| `pipeline/commands/extract_pdf.py` | +53 lines — Google Vision import, `_ocr_page_google_vision()`, `_check_google_vision()`, OCR dispatch logic |
| `lib/build-runner.ts` | +35 lines — `os` import, `_writeGoogleVisionCredsTempFile()`, `_deleteGoogleVisionCredsTempFile()`, env injection in `runStep` and `_spawnPipeline`, cleanup on exit/error |
| `lib/db-schema.ts` | +2 lines — seed + migration-safe INSERT for `google_vision_credentials` setting |
| `app/settings/page.tsx` | +20 lines — `ScanText` icon, `Textarea` import, OCR Settings section |
| `Dockerfile` | +2 lines — `google-cloud-vision>=3.7.0` pip install |
| `pipeline/requirements.txt` | +1 line — `google-cloud-vision>=3.7.0` |
| `components/ui/textarea.tsx` | created — minimal shadcn-style Textarea component (18 lines) |

## Tasks Completed

- [x] Python: `try/except ImportError` guard for `google.cloud.vision`
- [x] Python: `_ocr_page_google_vision(image_bytes)` using `document_text_detection`
- [x] Python: `_check_google_vision()` checks env + file existence
- [x] Python: OCR dispatch — Google Vision (ThreadPoolExecutor 5) if available, else Tesseract fallback
- [x] Python: All existing Tesseract logic preserved intact
- [x] TS: `_writeGoogleVisionCredsTempFile()` writes DB credentials to temp file (mode 0o600)
- [x] TS: `_deleteGoogleVisionCredsTempFile()` cleanup on exit and error
- [x] TS: `GOOGLE_APPLICATION_CREDENTIALS` injected into both PDF pre-step env and pipeline spawn env
- [x] TS: Temp file cleaned up after pre-processing chain AND after pipeline exits/errors
- [x] DB: `google_vision_credentials` seeded in fresh DBs and migration-safe for existing DBs
- [x] Settings UI: OCR Settings section with Textarea, placeholder, and help text
- [x] Dockerfile: `google-cloud-vision>=3.7.0` added
- [x] requirements.txt: `google-cloud-vision>=3.7.0` added
- [x] TypeScript compile: `npx tsc --noEmit` — PASS (zero errors)

## Tests Status
- Type check: PASS (zero errors)
- Unit tests: not run (no test changes required)

## Issues Encountered
- Initial `Record<string, string | undefined>` type for spawn `env` conflicted with `NodeJS.ProcessEnv` — fixed by using `NodeJS.ProcessEnv` type directly with spread conditional.
- `Textarea` UI component missing from `components/ui/` — created minimal version matching existing `Input` pattern.
- Removed unused `import io` inside the Google Vision branch.

## Next Steps
- User must paste Google Cloud Vision JSON credentials in Settings > OCR Settings
- For Dockerfile, `google-cloud-vision` is installed separately after `requirements.txt` to avoid modifying that step; alternatively could be consolidated if `requirements.txt` is updated (it is — both approaches covered)
