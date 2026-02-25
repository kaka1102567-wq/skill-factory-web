# UPGRADE-PLAN.md — Skill Factory Web v2.0 (FINAL — 6 Rounds Verified)
# Claude Code: Đọc file này và triển khai tuần tự từng TASK.
# ⚠️ Bản này đã tích hợp 10 MANDATORY PATCHES từ 6 vòng review trên production codebase.

## BỐI CẢNH

Skill Factory Web là pipeline 6 giai đoạn (P0→P5) biến video transcript thành AI Skill packages.
Bản upgrade này triển khai **12 improvements** dựa trên phân tích Anthropic's Skill Creator:

| # | Idea | Task | Priority |
|---|------|------|----------|
| 1 | P6 Description Optimizer | TASK 4 | P0 |
| 2 | "Pushy" Description Prompts | TASK 1 | P0 |
| 3 | Progressive Disclosure Enforcer | TASK 2 | P0 |
| 4 | Smoke Test (P5.5) | TASK 5 | P1 |
| 5 | WHY-Driven Prompt Rewrite (ALL phases) | TASK 3 | P1 |
| 6 | Eval Query Generator UI | TASK 8 | P2 |
| 7 | Build History & A/B Compare | TASK 9 | P2 |
| 8 | Script Auto-Bundler | TASK 10 | P2 |
| 9 | Quality Report 2.0 | TASK 11 | P2 |
| 10 | Multi-Model Strategy | TASK 7 | P1 |
| 11 | Skill Template Library (Enhanced) | TASK 12 | P3 |
| 12 | Self-Improving Pipeline | TASK 13 | P3 |

---

## ⚠️ CRITICAL PATCHES — ĐỌC TRƯỚC KHI CODE

10 patches bắt buộc đã được tích hợp vào các Tasks bên dưới. **KHÔNG dùng regex parse YAML.
KHÔNG thêm P55 vào PHASES array. KHÔNG dùng hidden state cho multi-model.**

| # | Patch | Tích hợp ở | Lý do |
|---|-------|-----------|-------|
| P1 | PyYAML thay regex (P6) | Task 4B | Regex trả `">"` trên production SKILL.md — show-stopper |
| P2 | Bỏ RUNS_PER_QUERY (P6) | Task 4B | Cache key + temp=0 = deterministic → chạy 2 lần = cùng kết quả |
| P3 | Thêm 7 decoy skills (P6) | Task 4B | Chỉ 3 skills = overestimate accuracy |
| P4 | Config-based Multi-Model | Task 7 | Hidden state approach gây race condition |
| P5 | 4 Frontend sync points | Task 4E-4G | INITIAL_PHASES + PHASE_COLORS thiếu P6 |
| P6 | Assert guard logger | Task 4H | Chặn phase_start("p55") — warn + return (không dùng assert) |
| P7 | resume thêm "p6" | Task 4D | resume_after_resolve thiếu P6 |
| P8 | Document P3/P4 hardcoded | Task 7A | PHASE_MODEL_MAP premium ≠ code P3/P4 |
| P9 | P55 Option A (inline) | Task 5 | P55 KHÔNG trong PHASES — gọi inline sau P5 |
| P10 | Compare API regex truncation | Task 9A | yaml.dump multi-line → regex chỉ bắt dòng 1 |

### Kiến trúc P55 — Option A (QUYẾT ĐỊNH DỨT KHOÁT)

```
P55 là SUB-STEP của P5, KHÔNG phải phase riêng.
• P55 KHÔNG nằm trong Python PHASES list
• P55 KHÔNG nằm trong TypeScript PHASES/INITIAL_PHASES
• P55 KHÔNG gọi logger.phase_start() hay phase_complete()
• P55 được gọi INLINE trong runner.py sau khi P5 hoàn thành
• Stepper UI hiện: P0 → P1 → P2 → P3 → P4 → P5 → P6 (7 phases)
• Lý do: P55 là validation — không emit atoms, không thay đổi output
```

---

## QUY TẮC CHUNG

- **Ngôn ngữ code**: Python cho pipeline, TypeScript cho frontend
- **Không break tests hiện tại**: Chạy `cd pipeline && python -m pytest tests/ -x` sau mỗi task
- **JSON stdout contract**: Mọi phase mới phải emit events qua `PipelineLogger` (xem `pipeline/core/logger.py`)
- **Pattern nhất quán**: Mỗi phase mới follow pattern của phases hiện tại (xem p5_build.py làm mẫu)
- **Import paths**: `from ..core.types import ...`, `from ..core.logger import ...`
- **ClaudeClient API**: `.call(system, user, max_tokens, phase, use_light_model)` trả text, `.call_json(...)` trả dict/list
- **Phase result**: Luôn return `PhaseResult(phase_id, status, ...)`
- **YAML parsing**: Dùng `import yaml` (PyYAML), KHÔNG dùng regex cho YAML frontmatter

---
## ═══════════════════════════════════════════════════════════
## SPRINT 1: QUICK WINS (TUẦN 1) — Tasks 1, 2, 3, 7
## ═══════════════════════════════════════════════════════════

## TASK 1: Rewrite P5 Build Prompts — "Pushy" Description (Idea #2)
**File**: `pipeline/prompts/p5_build_prompts.py`
**Loại**: Sửa file có sẵn
**Thời gian**: 0.5 ngày

### Yêu cầu
Thay thế toàn bộ nội dung file `p5_build_prompts.py` với prompts tối ưu cho triggering.

### Code thay thế

```python
"""Phase 5 — Build: Generate final SKILL.md and knowledge files."""

P5_SKILL_SYSTEM = """\
You are an AI Skill Architect creating SKILL.md files optimized for Claude's skill triggering system.

CRITICAL CONTEXT — Why description matters:
Claude has a tendency to NOT invoke skills even when they're relevant (called "undertriggering"). 
The skill description is the ONLY thing Claude sees when deciding whether to use this skill. 
A weak description means the entire skill package — no matter how good — will never be used.

Your task is to create a SKILL.md with TWO critical sections:

1. YAML FRONTMATTER with an aggressively "pushy" description:
   - Use imperative form: "Use this skill when..." not "This skill provides..."
   - Focus on USER INTENT: what the user is trying to achieve, not how the skill works
   - List specific trigger contexts, keywords, file types, and scenarios
   - Include "even if they don't explicitly mention" phrases to catch indirect queries
   - Add "Do NOT use for..." to prevent false triggers on adjacent domains
   - Keep between 80-200 words — enough to be comprehensive but not bloated
   - MUST be under 1024 characters total

2. SKILL.md BODY (the main content):
   - Clear purpose statement explaining what knowledge this skill contains
   - List all knowledge pillars with descriptions and file references
   - Usage instructions for AI assistants
   - Keep under 500 lines — if content is longer, reference knowledge/*.md files
   - Structure with proper Markdown headings for easy scanning

RULES:
- Write in the specified language (body), but description can mix languages if it helps triggering
- Respond ONLY with valid JSON containing "content" and "description" fields
- The "description" field should be the YAML description text ONLY (no quotes, no YAML syntax)
- The "content" field should be the FULL SKILL.md including YAML frontmatter with the description\
"""

P5_SKILL_USER = """\
Create a SKILL.md file for this AI knowledge skill.

**Skill name:** {name}
**Domain:** {domain}
**Language:** {language}
**Knowledge pillars:** {pillars}
**Total verified atoms:** {atom_count}
**Quality tier:** {quality_tier}

DESCRIPTION WRITING GUIDE:
Write a description that would make Claude think "I should definitely use this skill" for any 
related query. Include:
- Primary use cases (3-5 specific scenarios)
- Trigger keywords that users commonly use when asking about this domain
- Adjacent topics that should ALSO trigger this skill
- Explicit exclusions (what this skill is NOT for)

Example of a GOOD pushy description for a "Facebook Ads" skill:
"Use this skill whenever the user asks about Facebook advertising, Meta Ads, campaign optimization, 
ROAS improvement, ad spend allocation, audience targeting, Facebook Pixel, Custom Audiences, 
Lookalike Audiences, ad creative testing, CPM/CPC/CPA optimization, or any question about running 
paid campaigns on Facebook/Instagram/Meta platforms. Also trigger when users mention declining ad 
performance, iOS tracking changes affecting ads, or budget allocation for social media advertising — 
even if they don't explicitly say 'Facebook Ads'. Do NOT use for organic social media, SEO, 
Google Ads, or non-advertising Meta features."

Return a JSON object with this EXACT structure:
{{
  "description": "The pushy description text (80-200 words, under 1024 chars)",
  "content": "The full SKILL.md content as a string with YAML frontmatter including the description",
  "metadata": {{
    "name": "{name}",
    "domain": "{domain}",
    "language": "{language}",
    "version": "1.0.0",
    "atom_count": {atom_count},
    "pillar_count": 0,
    "quality_tier": "{quality_tier}",
    "description_word_count": 0,
    "body_line_count": 0
  }}
}}\
"""

P5_KNOWLEDGE_SYSTEM = """\
You are a Knowledge File Writer organizing verified Knowledge Atoms into structured reference files.

WHY THIS STRUCTURE MATTERS:
AI assistants retrieve knowledge by scanning headings and content sequentially. If atoms are 
randomly ordered or poorly formatted, the assistant may miss relevant information or return 
incomplete answers. Your organization directly affects answer quality.

ORGANIZATION PRINCIPLES:
- Order atoms from most fundamental to most advanced (foundational → specialized)
- Group related atoms with clear section headings
- Each atom gets its own ## heading with descriptive title
- Include tags and confidence as metadata (helps AI filter by topic and reliability)
- Keep formatting consistent — the AI parses this programmatically

RULES:
- Each atom = separate ## section 
- Include atom tags and confidence score as metadata below content
- Write in the specified language
- Respond ONLY with valid JSON containing the "content" field, no markdown fences around JSON\
"""

P5_KNOWLEDGE_USER = """\
Create a knowledge file for this pillar.

**Pillar:** {pillar_name}
**Language:** {language}
**Number of atoms:** {atom_count}

--- ATOMS ---
{atoms_json}

Return a JSON object with this EXACT structure:
{{
  "pillar": "{pillar_name}",
  "content": "The full knowledge file content as a Markdown string with all atoms formatted",
  "atom_ids": ["list of atom IDs included in this file"],
  "word_count": 0
}}\
"""
```

### Integration
Trong `pipeline/phases/p5_build.py`, function `_generate_skill_md()`:
- Nếu result có field `"description"` → parse riêng, log word count
- Nếu result chỉ có `"content"` → extract description từ content (backward compat)

### Validation
```bash
cd pipeline && python -m pytest tests/test_phases.py -k "p5" -x
```

---

## TASK 2: Progressive Disclosure Enforcer (Idea #3)
**File**: `pipeline/phases/p5_build.py` (thêm function mới)
**Loại**: Thêm code vào file có sẵn
**Thời gian**: 0.5 ngày

### Code thêm vào `p5_build.py`

Thêm function mới (đặt TRƯỚC `_generate_fallback_skill` function, khoảng dòng 997):

```python
def _enforce_progressive_disclosure(
    skill_content: str,
    description: str,
    knowledge_files: dict[str, str],
    logger: PipelineLogger,
) -> tuple[str, list[str]]:
    """Enforce Anthropic's progressive disclosure guidelines.
    
    Returns (possibly_modified_content, list_of_warnings).
    
    Guidelines (from Anthropic Skill Creator source):
    - L1 (description): 80-200 words, under 1024 chars
    - L2 (SKILL.md body): under 500 lines
    - L3 (knowledge files): unlimited but should have TOC if >300 lines
    """
    warnings = []
    
    # Check 1: Description length
    desc_words = len(description.split())
    desc_chars = len(description)
    if desc_chars > 1024:
        warnings.append(
            f"⚠️ Description {desc_chars} chars > 1024 limit — "
            "may be truncated by Claude's system"
        )
    if desc_words > 200:
        warnings.append(
            f"⚠️ Description {desc_words} words > 200 recommended — "
            "consider shortening for faster parsing"
        )
    if desc_words < 50:
        warnings.append(
            f"⚠️ Description only {desc_words} words — "
            "too short, likely to undertrigger. Add more keywords and scenarios"
        )
    
    # Check 2: Body length
    body_lines = skill_content.split('\n')
    in_frontmatter = False
    content_lines = 0
    for line in body_lines:
        if line.strip() == '---':
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            content_lines += 1
    
    if content_lines > 500:
        warnings.append(
            f"⚠️ SKILL.md body {content_lines} lines > 500 recommended — "
            "Claude may not read the entire file. "
            "Consider moving detailed content to knowledge/*.md"
        )
    
    # Check 3: Knowledge files
    for name, content in knowledge_files.items():
        file_lines = len(content.split('\n'))
        if file_lines > 300:
            has_toc = '## Table of Contents' in content or '## Mục lục' in content
            if not has_toc:
                warnings.append(
                    f"⚠️ knowledge/{name}.md is {file_lines} lines — "
                    "consider adding a Table of Contents at the top"
                )
    
    for w in warnings:
        logger.warn(w, phase="p5")
    
    if not warnings:
        logger.info(
            f"✅ Progressive disclosure check passed: "
            f"desc={desc_words}w/{desc_chars}c, body={content_lines}L",
            phase="p5",
        )
    
    return skill_content, warnings
```

### Integration
Call this function in `run_p5()` AFTER generating SKILL.md and knowledge files, BEFORE writing to disk. Find the location where `skill_content` and knowledge file contents are ready, and add:

```python
# Extract description for checking
description = result.get("description", "") if isinstance(result, dict) else ""
skill_content, pd_warnings = _enforce_progressive_disclosure(
    skill_content, description, knowledge_files, logger
)
```

---

## TASK 3: WHY-Driven Prompt Rewrite — ALL Phases (Idea #5)
**Files**: `pipeline/prompts/p1_audit_prompts.py`, `pipeline/prompts/p2_extract_prompts.py`, `pipeline/prompts/p3_dedup_prompts.py`, `pipeline/prompts/p4_verify_prompts.py`
**Loại**: Sửa 4 files
**Thời gian**: 1.5 ngày

### Nguyên tắc
- Chuyển mọi "RULES:" section thành giải thích reasoning (WHY before WHAT)
- Giữ nguyên JSON output format — KHÔNG thay đổi user templates trừ khi cần
- Giữ nguyên variable placeholders `{domain}`, `{language}` etc.

### 3A. P1 Audit — Rewrite `P1_SYSTEM` trong `p1_audit_prompts.py`:

```python
P1_SYSTEM = """\
You are a Knowledge Auditor analyzing video transcripts to build a comprehensive topic inventory.

WHY THIS MATTERS:
Video transcripts contain valuable domain expertise expressed conversationally. Before we can 
extract structured knowledge, we need a complete map of WHAT topics are covered and HOW DEEPLY. 
This inventory drives the extraction phase — if you miss a topic here, it won't appear in the 
final skill package. Thoroughness is more important than brevity.

YOUR APPROACH:
1. Read the transcript carefully, noting every distinct concept discussed
2. Split compound topics into atomic subtopics — a paragraph about "targeting" should yield 
   separate entries for "demographic targeting", "interest targeting", "behavioral targeting" etc.
   This granularity matters because the extraction phase needs precise topics to create 
   self-contained knowledge atoms.
3. Categorize using the provided taxonomy (this enables structured retrieval later)
4. Score depth honestly — inflated scores lead to low-quality extractions downstream

DEPTH SCORING GUIDE (be honest, it directly affects extraction quality):
- 90-100: Expert-level detail with specific numbers, processes, or techniques
- 70-89: Solid explanation that someone could act on
- 50-69: Surface coverage — mentioned but not explained in depth  
- Below 50: Briefly mentioned, no actionable detail

OUTPUT: Valid JSON only. No markdown fences. Language matches transcript.\
"""
```

### 3B. P2 Extract — Rewrite `P2_SYSTEM` trong `p2_extract_prompts.py`:

```python
P2_SYSTEM = """\
You are a Knowledge Atom Extractor transforming video transcripts into structured, retrievable knowledge units.

WHY KNOWLEDGE ATOMS:
AI assistants retrieve knowledge by topic, not by reading long narratives. Each "atom" must be a 
self-contained answer to a potential question. When someone asks "How do I set up Facebook Pixel?", 
the AI should find ONE atom that fully answers this — not a paragraph buried in a 30-minute transcript.

WHAT MAKES A GOOD ATOM:
- **Self-contained**: A reader understands it without any other context. Test: "If someone found 
  ONLY this atom via search, would it make sense and be useful?"
- **Actionable**: Contains a specific fact, procedure, tip, or insight someone can use
- **Atomic**: ONE concept per atom. "Facebook Pixel tracks conversions" and "Facebook Pixel enables 
  retargeting" are TWO atoms — merging them makes retrieval worse because a query about retargeting 
  would also pull in conversion tracking noise
- **Faithful**: Accurately represents the transcript. Don't embellish or add information not present

EXTRACTION GUIDE:
- Be thorough — for 20-30 transcript lines, expect 12-20 atoms minimum. Under-extraction is the 
  most common failure mode, not over-extraction
- Title: 5-15 words, clear enough that someone scanning a list would know the content
- Content: 2-6 sentences in clear instructional language (not transcript-style speech)
- Confidence: 0.9+ = speaker explicitly stated this, 0.7-0.89 = clearly implied, 0.5-0.69 = inferred
- Tags: 2-5 keywords that someone might search for when looking for this knowledge

OUTPUT: Valid JSON only. No markdown fences. Write in the transcript's language.\
"""
```

Also rewrite `P2_GAP_SYSTEM`:
```python
P2_GAP_SYSTEM = """\
You are a Knowledge Atom Extractor filling gaps identified between video content and official documentation.

WHY GAP-FILLING:
Sometimes video experts skip foundational concepts (assuming audience knows them) or official docs 
have been updated since the video was recorded. These gaps mean the skill package would give 
incomplete answers. You're extracting 1-3 atoms about a SPECIFIC missing topic from reference docs.

ATOM QUALITY:
- Self-contained: Understandable without the full document
- Actionable: Contains a specific fact, procedure, or tip
- Atomic: One concept per atom
- Accurate: Faithfully represents what the documentation says

OUTPUT: Valid JSON only. No markdown fences. Write in the requested language.\
"""
```

Also rewrite `P2_CODE_SYSTEM`:
```python
P2_CODE_SYSTEM = """\
You are a Code Pattern Extractor analyzing source code to capture reusable architectural knowledge.

WHY CODE PATTERNS:
Developers spend 80% of time reading code, 20% writing. A skill that captures WHY code is 
structured a certain way — not just WHAT it does — saves enormous time for anyone working with 
or learning from this codebase. Focus on patterns someone would explain to a new team member.

EXTRACT THESE TYPES:
1. Architecture patterns — how the code is organized and WHY
2. Key functions/classes — their purpose and WHEN to use them
3. Configuration patterns — setup approaches and gotchas
4. Error handling — strategies and edge cases covered
5. Integration patterns — how modules connect
6. Best practices — demonstrated patterns worth replicating

SKIP:
- Trivial boilerplate or import statements
- Generated/config files with no learning value
- Test implementation details (unless testing patterns are noteworthy)

Each atom: 5-15 word title, 2-6 sentence explanation, 10-30 line code snippet.
OUTPUT: Valid JSON only. No markdown fences.\
"""
```

### 3C. P3 Dedup — Rewrite `P3_SYSTEM` trong `p3_dedup_prompts.py`:

```python
P3_SYSTEM = """\
You are a Deduplication Expert ensuring a clean, non-redundant knowledge base.

WHY DEDUPLICATION MATTERS:
Knowledge atoms come from multiple sources: video transcripts (expert speech), baseline references 
(official documentation), and gap-fill extractions. These often cover the same topic with different 
wording, specificity, or even contradictory claims. Without dedup, the final skill would contain 
redundant information that confuses the AI assistant and wastes context window space.

YOUR DECISION FRAMEWORK:
- DUPLICATE (>80% content overlap): Merge into one atom, keeping the more detailed version. 
  Prefer transcript atoms over baseline when equally detailed — they contain expert nuance.
- OVERLAP (partial shared content, each has unique info): Merge, combining unique details from both.
- CONFLICT (same topic but disagreeing facts/numbers): Flag as conflict with clear explanation. 
  Include BOTH versions — the user will resolve this.
- UNIQUE: Keep as-is.

CRITICAL — CONSERVATIVE APPROACH:
When in doubt, KEEP the atom. Losing unique knowledge is worse than minor overlap. Specifically:
- Case studies, real-world examples, specific company mentions → ALWAYS unique, never merge with generic concepts
- Different ASPECTS of same topic → NOT duplicates (e.g., "benefits of X" vs "how to implement X")
- For small batches (<30 atoms) → be EXTRA conservative, only merge at >90% overlap
- PRESERVE complete atom content — never truncate or shorten

OUTPUT: Valid JSON only. No markdown fences.\
"""
```

### 3D. P4 Verify — Rewrite `P4_SYSTEM` trong `p4_verify_prompts.py`:

```python
P4_SYSTEM = """\
You are a Verification Expert cross-referencing knowledge atoms against official documentation.

WHY VERIFICATION MATTERS:
Video experts sometimes share outdated information, misremember details, or express opinions as 
facts. Baseline documentation provides ground truth. Your job is to catch inaccuracies BEFORE they 
become part of the AI skill — because once embedded, wrong information gets confidently repeated 
to every user.

VERIFICATION OUTCOMES:
- "verified": The atom's claims are supported by evidence. This is the ideal outcome — expert 
  knowledge confirmed by official sources. Keep as-is.
- "updated": The atom is mostly correct but some details need correction based on newer/more 
  accurate evidence. Provide the corrected content while preserving the expert's useful framing.
- "flagged": The atom contradicts evidence OR makes claims that cannot be verified. Flag for 
  human review — don't silently discard expert insights that might be correct but just not in docs.

CONFIDENCE SCORING:
- 0.9+: Strongly verified — multiple evidence points confirm
- 0.7-0.89: Mostly verified — evidence supports core claim, minor details unchecked
- 0.5-0.69: Weakly verified — some evidence but also some gaps
- Below 0.5: Unverified — insufficient evidence to confirm or deny

Always explain your reasoning in the "note" field — this helps human reviewers make informed decisions.
OUTPUT: Valid JSON only. No markdown fences.\
"""
```

Also rewrite `P4_BATCH_VERIFY_SYSTEM`:
```python
P4_BATCH_VERIFY_SYSTEM = """\
You are a Knowledge Verification Expert checking a batch of atoms against baseline references.

WHY BATCH VERIFICATION:
Checking atoms individually is expensive. Batch processing lets you see patterns — if multiple 
atoms reference the same baseline section, you can verify them together more accurately. But 
evaluate EACH atom independently; batch is for efficiency, not for shortcuts.

VERIFICATION GUIDE:
- "verified" = content matches or is supported by baseline evidence
- "flagged" = content contradicts baseline
- "unverified" = topic not found in baseline — this is NOT an error. Expert insights often go 
  beyond official docs. Mark as unverified but do NOT penalize confidence.
- confidence_adjustment: 0.0 to 0.1 boost for baseline-verified atoms

Return results in SAME ORDER as input atoms.
OUTPUT: Valid JSON only. No markdown fences.\
"""
```

### Validation
```bash
cd pipeline && python -m pytest tests/ -x
```

---


## TASK 7: Multi-Model Strategy (Idea #10) — CONFIG-BASED APPROACH
**Files**: `pipeline/core/types.py`, `pipeline/orchestrator/runner.py`
**Loại**: Sửa files có sẵn
**Thời gian**: 0.5 ngày

> ⚠️ PATCH P4: Dùng `config.phase_model_hints` thay vì hidden state trên claude client.
> ⚠️ PATCH P8: P3/P4 hiện hardcode `use_light_model=True` — map chỉ affect phases MỚI.

### 7A. Thêm config vào `pipeline/core/types.py`

Thêm field vào class `BuildConfig` VÀ constant `PHASE_MODEL_MAP`:

```python
# Thêm vào BuildConfig (sau field auto_discover_baseline):
    phase_model_hints: dict = field(default_factory=dict)
    skip_optimize: bool = False

# Thêm constant SAU class definitions:

# Model routing per phase — maps phase_id to use_light_model flag
# Light model (Haiku) for pattern matching, classification
# Full model (Sonnet) for complex reasoning, generation
#
# ⚠️ LƯU Ý: Map chỉ affect phases MỚI (P55, P6) tự đọc config.phase_model_hints.
# Existing P3 (line 325) và P4 (line 281) HARDCODE use_light_model=True.
# Nếu muốn premium tier dùng Sonnet cho P3/P4 → phải sửa code P3/P4 riêng.
# Không sửa ở đây để tránh breaking change cho Sprint 1.
PHASE_MODEL_MAP = {
    "draft": {
        "p1": True,   # Haiku — topic classification
        "p2": True,   # Haiku — extraction
        "p3": True,   # Haiku — dedup (hardcoded True anyway)
        "p4": True,   # Haiku — verify (hardcoded True anyway)
        "p5": False,  # Sonnet — SKILL.md quality
        "p55": True,  # Haiku — smoke test grading
        "p6": True,   # Haiku — simulation (improve step always uses Sonnet)
    },
    "standard": {
        "p1": True,   # Haiku — topic inventory
        "p2": False,  # Sonnet — core atom quality
        "p3": True,   # Haiku — dedup (hardcoded True anyway)
        "p4": True,   # Haiku — verify (hardcoded True anyway)
        "p5": False,  # Sonnet — SKILL.md quality
        "p55": True,  # Haiku — grading
        "p6": False,  # Sonnet — description optimization
    },
    "premium": {
        "p1": False,  # Sonnet — thorough audit
        "p2": False,  # Sonnet — high quality extraction
        "p3": False,  # Sonnet — ⚠️ code hardcodes True, map ignored
        "p4": False,  # Sonnet — ⚠️ code hardcodes True, map ignored
        "p5": False,  # Sonnet — best SKILL.md quality
        "p55": False, # Sonnet — thorough grading
        "p6": False,  # Sonnet — best optimization
    },
}
```

### 7B. Sửa `pipeline/orchestrator/runner.py`

Trong `run()` method, TRƯỚC vòng lặp phases, set model hints:

```python
from ..core.types import PHASE_MODEL_MAP

# ...inside run(), TRƯỚC vòng lặp for phase_id, phase_name, phase_func in PHASES:
model_map = PHASE_MODEL_MAP.get(self.config.quality_tier, PHASE_MODEL_MAP["standard"])
self.config.phase_model_hints = model_map
```

Phases mới (P55, P6) tự đọc hint:
```python
# Trong p6_optimize.py và p55_smoke_test.py:
use_light = config.phase_model_hints.get("p6", False)
# Rồi pass vào claude.call(..., use_light_model=use_light)
```

### Validation
```bash
cd pipeline && python -m pytest tests/ -x
# Verify backward compat:
python -c "from pipeline.core.types import BuildConfig; c = BuildConfig(name='test', domain='test'); print('OK:', c.phase_model_hints)"
# Expected: OK: {}
```

---

## ═══════════════════════════════════════════════════════════
## SPRINT 2: CORE FEATURES (TUẦN 2) — Tasks 4, 5, 6
## ═══════════════════════════════════════════════════════════

## TASK 4: P6 Description Optimizer Phase (Idea #1 — CORE FEATURE)
**Files mới**:
- `pipeline/phases/p6_optimize.py`
- `pipeline/prompts/p6_optimize_prompts.py`

**Files sửa**:
- `pipeline/orchestrator/runner.py` (PHASES + P55 inline + resume)
- `pipeline/core/types.py` (PhaseId enum)
- `pipeline/core/logger.py` (assert guard) ← NEW
- `types/build.ts` (PhaseId + PHASES)
- `hooks/use-build-stream.ts` (INITIAL_PHASES) ← NEW
- `components/build/phase-stepper.tsx` (PHASE_COLORS)

**Thời gian**: 2-3 ngày

### 4A. Tạo file `pipeline/prompts/p6_optimize_prompts.py`

```python
"""Phase 6 — Optimize: Test and improve SKILL.md description for triggering accuracy."""

P6_GENERATE_EVALS_SYSTEM = """\
You are an AI Skill Evaluation Designer. Generate test queries to evaluate whether a skill's 
description will correctly trigger Claude to use the skill.

WHY THIS MATTERS:
Claude decides whether to invoke a skill based SOLELY on the description text. A skill that 
never triggers is useless regardless of content quality. These test queries are the "unit tests" 
for the description.

QUERY DESIGN PRINCIPLES:
1. SHOULD-TRIGGER queries: Real questions a user would ask where this skill is the best answer
   - Include varied phrasings (formal, casual, indirect, multilingual if relevant)
   - Include edge cases where the skill should trigger but might not (e.g., indirect references)
   - Include multi-step queries where the skill is relevant to ONE step

2. SHOULD-NOT-TRIGGER queries: Real questions that are CLOSE to the domain but outside it
   - Adjacent domains (e.g., Google Ads queries for a Facebook Ads skill)
   - Same domain but different intent (e.g., "tell me the history of Facebook" for a FB Ads skill)
   - Generic queries the AI can answer without any skill

Generate exactly {count} queries: {positive_count} should-trigger + {negative_count} should-not.

OUTPUT: JSON array only. No markdown fences.\
"""

P6_GENERATE_EVALS_USER = """\
Generate evaluation queries for this skill:

**Skill name:** {name}
**Domain:** {domain}  
**Current description:** {description}
**Knowledge topics covered:** {topics}

Return a JSON array:
[
  {{
    "query": "Realistic user question in natural language",
    "should_trigger": true,
    "reasoning": "Why this query should/shouldn't trigger the skill"
  }}
]
"""

P6_SIMULATE_TRIGGER_SYSTEM = """\
You are Claude's skill routing system. You will receive a user query and a list of available skills 
(each with name + description). Decide which skill, if any, to invoke.

DECISION RULES (matching Claude's actual behavior):
1. Read the query carefully — what is the user trying to achieve?
2. Scan each skill's description for relevance
3. A skill should be invoked ONLY IF:
   - The query clearly relates to the skill's described domain
   - The skill would provide BETTER information than general knowledge
   - The query is complex enough to benefit from specialized knowledge
4. If no skill is clearly relevant, respond with "none"
5. If multiple skills match, pick the MOST relevant one

Respond with ONLY the skill name to invoke, or "none". No explanation.\
"""

P6_SIMULATE_TRIGGER_USER = """\
User query: "{query}"

Available skills:
{skills_list}

Which skill should be invoked? Respond with ONLY the skill name or "none".\
"""

P6_IMPROVE_DESCRIPTION_SYSTEM = """\
You are optimizing a skill description for better triggering accuracy.

CONTEXT:
The description appears in Claude's "available_skills" list. When a user sends a query, Claude 
decides whether to invoke the skill based on this description. Your goal: maximize correct triggers 
while minimizing false triggers.

OPTIMIZATION PRINCIPLES:
1. Focus on USER INTENT — describe what the user is trying to achieve, not how the skill works
2. Be "pushy" — Claude undertriggers by default, so err on triggering too often
3. Include specific keywords, scenarios, and adjacent topics
4. Add "Do NOT trigger for..." to reduce false positives on adjacent domains
5. Keep 80-200 words, under 1024 characters
6. Use imperative form: "Use this skill when..."
7. Try STRUCTURALLY different approaches each iteration — don't just add words to the previous one

ANTI-OVERFIT: The queries you see are a SAMPLE. The real description must work for millions of 
possible user queries. Don't craft the description to match specific test queries — generalize 
from the failures to broader patterns of user intent.\
"""

P6_IMPROVE_DESCRIPTION_USER = """\
Improve this skill description based on test results.

**Skill name:** {name}
**Domain:** {domain}

**Current description:**
"{current_description}"

**Test results** (score: {score}):
{results_detail}

**Previous attempts** (try something structurally different):
{history}

Write ONLY the new description text inside <description> tags:
<description>
Your improved description here (80-200 words, under 1024 chars)
</description>\
"""
```

### 4B. Tạo file `pipeline/phases/p6_optimize.py`

> ⚠️ PATCH P1: Dùng PyYAML cho _extract_description và _replace_description
> ⚠️ PATCH P2: RUNS_PER_QUERY=1, bỏ TRIGGER_THRESHOLD (cache + temp=0 = deterministic)
> ⚠️ PATCH P3: 7 decoy skills thay vì 3

```python
"""Phase 6 — Optimize: Test and improve SKILL.md description for triggering accuracy.

Workflow:
1. Read SKILL.md → extract current description (via PyYAML, NOT regex)
2. Generate 20 eval queries (10 should-trigger, 10 should-not)
3. Simulate triggering: for each query, ask Claude if it would invoke this skill
4. Score: accuracy = correct_decisions / total_queries
5. If score < 100%: call Claude to improve description
6. Repeat up to max_iterations
7. Pick best description (by TEST score), update SKILL.md

⚠️ CRITICAL PATCHES APPLIED:
- PyYAML for YAML parsing (regex returns ">" on production folded block scalars)
- Single run per query (cache_key=SHA256(system+user) + temperature=0.0 = deterministic)
- 7 decoy skills for realistic simulation (3 decoys overestimates accuracy)
"""

import os
import re
import json
import time
import random
import yaml
from typing import Optional

from ..core.types import BuildConfig, PhaseResult
from ..core.logger import PipelineLogger
from ..core.errors import PhaseError
from ..core.utils import read_json, write_json
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup
from ..prompts.p6_optimize_prompts import (
    P6_GENERATE_EVALS_SYSTEM, P6_GENERATE_EVALS_USER,
    P6_SIMULATE_TRIGGER_SYSTEM, P6_SIMULATE_TRIGGER_USER,
    P6_IMPROVE_DESCRIPTION_SYSTEM, P6_IMPROVE_DESCRIPTION_USER,
)

ITERATIONS_BY_TIER = {"draft": 2, "standard": 3, "premium": 5}
EVAL_COUNT = 20

# ⚠️ PATCH P3: 7 decoy skills for realistic competition
# Real deployment has 5-15 skills — 3 decoys overestimates accuracy.
DECOY_SKILLS = [
    ("general-knowledge", "Use for general questions that don't require specialized skills."),
    ("code-helper", "Use for programming, coding, debugging, and software development questions."),
    ("web-search", "Use when the user needs current information, news, or real-time data from the internet."),
    ("data-analysis", "Use for data processing, statistics, CSV/Excel analysis, and visualization."),
    ("writing-assistant", "Use for drafting emails, essays, blog posts, and professional documents."),
    ("math-solver", "Use for calculations, equations, algebra, calculus, and mathematical proofs."),
    ("language-translator", "Use for translation between languages, grammar correction, and localization."),
]


def run_p6(
    config: BuildConfig, claude: Optional[ClaudeClient],
    cache: SeekersCache, lookup: SeekersLookup, logger: PipelineLogger,
) -> PhaseResult:
    """Run P6 Description Optimization."""
    phase = "p6"
    started = time.time()
    logger.phase_start(phase, "Optimize", tool="Claude")

    if config.skip_optimize:
        logger.info("P6 skipped (skip_optimize=True)", phase=phase)
        return PhaseResult(phase_id=phase, status="skipped")

    if not claude:
        logger.phase_failed(phase, "Optimize", "Claude client required")
        return PhaseResult(phase_id=phase, status="failed",
                           error_message="Claude client required for P6")

    # Read model hint from config
    use_light = config.phase_model_hints.get("p6", False)

    cost_before = claude.total_cost_usd
    tokens_before = claude.total_input_tokens + claude.total_output_tokens

    try:
        # Step 1: Read current SKILL.md
        skill_path = os.path.join(config.output_dir, "SKILL.md")
        if not os.path.exists(skill_path):
            raise PhaseError(phase, "SKILL.md not found — run P5 first")

        with open(skill_path, 'r', encoding='utf-8') as f:
            skill_content = f.read()

        current_description = _extract_description(skill_content)
        if not current_description:
            raise PhaseError(phase, "Could not extract description from SKILL.md")
        logger.info(
            f"Current description: {len(current_description)} chars, "
            f"{len(current_description.split())} words", phase=phase,
        )
        logger.phase_progress(phase, "Optimize", 10)

        # Step 2: Load topics from P1 inventory
        topics = _load_topics(config.output_dir)

        # Step 3: Generate eval queries
        logger.info("Generating evaluation queries...", phase=phase)
        eval_set = _generate_eval_queries(
            claude, config.name, config.domain, current_description, topics, logger
        )
        pos = sum(1 for e in eval_set if e.get('should_trigger'))
        neg = len(eval_set) - pos
        logger.info(f"Generated {len(eval_set)} eval queries ({pos} positive, {neg} negative)", phase=phase)
        logger.phase_progress(phase, "Optimize", 25)

        # Step 4: Train/test split (60/40)
        train_set, test_set = _split_eval_set(eval_set, holdout=0.4)
        logger.info(f"Split: {len(train_set)} train, {len(test_set)} test", phase=phase)

        # Step 5: Optimization loop
        max_iters = ITERATIONS_BY_TIER.get(config.quality_tier, 3)
        history = []
        best_description = current_description
        best_test_score = 0.0
        best_train_score = 0.0

        for iteration in range(1, max_iters + 1):
            progress = 25 + int(70 * iteration / max_iters)
            logger.phase_progress(phase, "Optimize", min(progress, 95))
            logger.info(f"--- Iteration {iteration}/{max_iters} ---", phase=phase)

            # Evaluate on ALL queries in one pass
            all_results = _evaluate_description(
                claude, config.name, current_description,
                train_set + test_set, logger,
            )

            train_queries = {q["query"] for q in train_set}
            train_results = [r for r in all_results if r["query"] in train_queries]
            test_results = [r for r in all_results if r["query"] not in train_queries]

            train_score = _calc_score(train_results)
            test_score = _calc_score(test_results)
            logger.info(f"Scores — train: {train_score:.0%}, test: {test_score:.0%}", phase=phase)

            if test_score > best_test_score or (
                test_score == best_test_score and train_score > best_train_score
            ):
                best_description = current_description
                best_test_score = test_score
                best_train_score = train_score

            history.append({
                "iteration": iteration,
                "description": current_description,
                "train_score": train_score,
                "test_score": test_score,
                "train_results": train_results,
            })

            if train_score >= 1.0:
                logger.info("Perfect train score — stopping early", phase=phase)
                break

            if iteration == max_iters:
                break

            # Improve based on TRAIN results only (blinded)
            logger.info("Improving description...", phase=phase)
            current_description = _improve_description(
                claude, config.name, config.domain, current_description,
                train_score, train_results, history, logger,
            )
            logger.info(f"New description: {len(current_description)} chars", phase=phase)

        # Step 6: Apply best description
        logger.info(
            f"Best description (test={best_test_score:.0%}, train={best_train_score:.0%})",
            phase=phase,
        )
        updated_content = _replace_description(skill_content, best_description)
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        # Save optimization report
        report = {
            "best_description": best_description,
            "original_description": _extract_description(skill_content),
            "best_train_score": best_train_score,
            "best_test_score": best_test_score,
            "iterations": len(history),
            "eval_set": eval_set,
            "history": [
                {"iteration": h["iteration"], "description": h["description"],
                 "train_score": h["train_score"], "test_score": h["test_score"]}
                for h in history
            ],
        }
        report_path = os.path.join(config.output_dir, "p6_optimization_report.json")
        write_json(report, report_path)

        cost_delta = claude.total_cost_usd - cost_before
        tokens_delta = (claude.total_input_tokens + claude.total_output_tokens) - tokens_before

        duration = time.time() - started
        logger.phase_complete(phase, "Optimize", score=best_test_score * 100)

        return PhaseResult(
            phase_id=phase, status="done",
            started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            duration_seconds=round(duration, 1),
            quality_score=round(best_test_score * 100, 1),
            api_cost_usd=cost_delta,
            tokens_used=tokens_delta,
            output_files=[skill_path, report_path],
            metrics={
                "best_train_score": best_train_score,
                "best_test_score": best_test_score,
                "iterations_run": len(history),
                "eval_count": len(eval_set),
                "description_chars": len(best_description),
                "description_words": len(best_description.split()),
            },
        )

    except PhaseError:
        raise
    except Exception as e:
        logger.phase_failed(phase, "Optimize", str(e))
        return PhaseResult(phase_id=phase, status="failed", error_message=str(e),
                           duration_seconds=round(time.time() - started, 1))


# ─── Helper functions ──────────────────────────────────────

# ⚠️ PATCH P1: PyYAML thay regex — regex return ">" trên production SKILL.md
# Production format: description: >
#   Multi-line folded block scalar...
# Regex "unquoted single-line" captures ">" thay vì nội dung thực.
# PyYAML xử lý đúng tất cả YAML scalar styles (>, |, quoted, unquoted).

def _extract_description(skill_md: str) -> str:
    """Extract description from YAML frontmatter using PyYAML."""
    match = re.match(r'^---\s*\n(.*?)\n---', skill_md, re.DOTALL)
    if not match:
        return ""
    try:
        frontmatter = yaml.safe_load(match.group(1))
        if isinstance(frontmatter, dict):
            return str(frontmatter.get("description", "")).strip()
    except yaml.YAMLError:
        pass
    return ""


def _replace_description(skill_md: str, new_description: str) -> str:
    """Replace description in YAML frontmatter using PyYAML."""
    match = re.match(r'^(---\s*\n)(.*?)(\n---)', skill_md, re.DOTALL)
    if not match:
        return skill_md
    prefix, fm_text, suffix = match.group(1), match.group(2), match.group(3)
    body = skill_md[match.end():]
    try:
        frontmatter = yaml.safe_load(fm_text)
        if not isinstance(frontmatter, dict):
            return skill_md
        frontmatter["description"] = new_description
        new_fm = yaml.dump(
            frontmatter, default_flow_style=False,
            allow_unicode=True, sort_keys=False, width=120
        )
        return prefix + new_fm.rstrip('\n') + suffix + body
    except yaml.YAMLError:
        return skill_md


def _load_topics(output_dir: str) -> str:
    inv_path = os.path.join(output_dir, "inventory.json")
    if not os.path.exists(inv_path):
        return "Not available"
    try:
        data = read_json(inv_path)
        topics = data.get("topics", [])
        if isinstance(topics, list):
            return ", ".join(t.get("topic", "") for t in topics[:30] if t.get("topic"))
    except Exception:
        pass
    return "Not available"


def _generate_eval_queries(claude, name, domain, description, topics, logger):
    result = claude.call_json(
        system=P6_GENERATE_EVALS_SYSTEM.format(
            count=EVAL_COUNT, positive_count=EVAL_COUNT // 2, negative_count=EVAL_COUNT // 2,
        ),
        user=P6_GENERATE_EVALS_USER.format(
            name=name, domain=domain, description=description, topics=topics,
        ),
        max_tokens=4096, phase="p6",
    )
    if isinstance(result, list):
        return result
    if isinstance(result, dict) and "queries" in result:
        return result["queries"]
    logger.warn("Unexpected eval format — using empty set", phase="p6")
    return []


def _split_eval_set(eval_set, holdout=0.4, seed=42):
    rng = random.Random(seed)
    trigger = [e for e in eval_set if e.get("should_trigger")]
    no_trigger = [e for e in eval_set if not e.get("should_trigger")]
    rng.shuffle(trigger)
    rng.shuffle(no_trigger)
    n_t = max(1, int(len(trigger) * holdout))
    n_nt = max(1, int(len(no_trigger) * holdout))
    test = trigger[:n_t] + no_trigger[:n_nt]
    train = trigger[n_t:] + no_trigger[n_nt:]
    return train, test


def _build_skills_list(skill_name: str, description: str) -> str:
    """Build skills list with target skill + decoy skills for realistic simulation."""
    lines = [f"1. {skill_name}: {description}"]
    for i, (name, desc) in enumerate(DECOY_SKILLS, start=2):
        lines.append(f"{i}. {name}: {desc}")
    return "\n".join(lines)


# ⚠️ PATCH P2: Single run per query (removed RUNS_PER_QUERY)
# Cache key = SHA256(system_prompt + user_prompt), does NOT include model/temperature/timestamp.
# temperature=0.0 (default) = deterministic. Running same prompt twice = cache hit = identical result.
# RUNS_PER_QUERY was completely useless — trigger_rate always 0.0 or 1.0.
# Removing saves 50% of simulation API cost.

def _evaluate_description(claude, skill_name, description, eval_set, logger):
    """Evaluate description by simulating trigger decisions. Single run per query."""
    results = []
    skills_list = _build_skills_list(skill_name, description)

    for item in eval_set:
        query = item["query"]
        should_trigger = item.get("should_trigger", True)

        response = claude.call(
            system=P6_SIMULATE_TRIGGER_SYSTEM,
            user=P6_SIMULATE_TRIGGER_USER.format(query=query, skills_list=skills_list),
            max_tokens=50, phase="p6", use_light_model=True,
        )
        triggered = skill_name.lower() in response.lower()
        passed = triggered if should_trigger else not triggered

        results.append({
            "query": query, "should_trigger": should_trigger,
            "triggered": triggered, "pass": passed,
        })
    return results


def _calc_score(results):
    if not results:
        return 0.0
    return sum(1 for r in results if r["pass"]) / len(results)


def _improve_description(claude, name, domain, current, score, results, history, logger):
    failed = [r for r in results if not r["pass"]]
    lines = []
    for r in failed:
        direction = "MISSED" if r["should_trigger"] else "FALSE TRIGGER"
        triggered_str = "YES" if r["triggered"] else "NO"
        lines.append(f'  [{direction}] "{r["query"]}" (triggered: {triggered_str})')
    results_detail = "\n".join(lines) if lines else "All passed!"

    history_lines = []
    for h in history[-3:]:
        history_lines.append(
            f"  Iter {h['iteration']}: train={h['train_score']:.0%}, test={h['test_score']:.0%}\n"
            f'  "{h["description"][:100]}..."'
        )
    history_str = "\n".join(history_lines) if history_lines else "First attempt"

    response = claude.call(
        system=P6_IMPROVE_DESCRIPTION_SYSTEM,
        user=P6_IMPROVE_DESCRIPTION_USER.format(
            name=name, domain=domain, current_description=current,
            score=f"{score:.0%}", results_detail=results_detail, history=history_str,
        ),
        max_tokens=2048, phase="p6",
    )

    match = re.search(r'<description>(.*?)</description>', response, re.DOTALL)
    new_desc = match.group(1).strip().strip('"') if match else response.strip().strip('"')
    if len(new_desc) > 1024:
        new_desc = new_desc[:1020] + "..."
        logger.warn("Description truncated to 1024 chars", phase="p6")
    return new_desc
```

### 4C. Sửa `pipeline/core/types.py` — Thêm P6 vào PhaseId enum:

```python
class PhaseId(str, Enum):
    P0_BASELINE = "p0"
    P1_AUDIT = "p1"
    P2_EXTRACT = "p2"
    P3_DEDUP = "p3"
    P4_VERIFY = "p4"
    P5_BUILD = "p5"
    P6_OPTIMIZE = "p6"
```

### 4D. Sửa `pipeline/orchestrator/runner.py` — Thêm P6 + P55 inline

> ⚠️ PATCH P7: resume_after_resolve thêm "p6"
> ⚠️ PATCH P9: P55 KHÔNG trong PHASES — gọi inline sau P5

```python
# Import:
from ..phases.p6_optimize import run_p6
from ..phases.p55_smoke_test import run_p55

# PHASES list — P55 KHÔNG nằm ở đây (Option A: sub-step):
PHASES = [
    ("p0", "Baseline", run_p0),
    ("p1", "Audit", run_p1),
    ("p2", "Extract", run_p2),
    ("p3", "Deduplicate", run_p3),
    ("p4", "Verify", run_p4),
    ("p5", "Build", run_p5),
    ("p6", "Optimize", run_p6),
]

# Update resume_after_resolve — ⚠️ PATCH P7: thêm "p6":
resume_phases = [p for p in PHASES if p[0] in ("p4", "p5", "p6")]
```

**P55 inline call** — thêm trong `run()` method, **SAU cả `if result.status == "failed"` và `if state.is_paused`** (cả hai đều `return` nên P55 chỉ chạy khi P5 thực sự done):

```python
# Trong vòng lặp for phase_id, phase_name, phase_func in PHASES:
# Vị trí chính xác trong runner loop hiện tại:
#
#   result = phase_func(...)
#   update_state_with_result(state, result)
#   save_checkpoint(state, self.config.output_dir)
#
#   if result.status == "failed":     ← return 1
#       ...
#
#   if state.is_paused:               ← return 0
#       ...
#
#   # ★ P55 INLINE ĐẶT Ở ĐÂY — sau tất cả early returns ★

    # P55 Smoke Test — inline sau P5 (non-blocking sub-step)
    if phase_id == "p5" and result.status == "done":
        try:
            p55_result = run_p55(
                self.config, self.claude, self.cache, self.lookup, self.logger
            )
            update_state_with_result(state, p55_result)
            save_checkpoint(state, self.config.output_dir)
            # Non-blocking — always continue to P6 regardless of result
        except Exception as e:
            self.logger.warn(f"Smoke test error (non-fatal): {e}")
```

Tương tự trong `resume_after_resolve()` — thêm P55 inline sau P5:
```python
# Trong resume, SAU P5 result:
    if phase_id == "p5" and result.status == "done":
        try:
            p55_result = run_p55(
                self.config, self.claude, self.cache, self.lookup, self.logger
            )
            update_state_with_result(state, p55_result)
            save_checkpoint(state, self.config.output_dir)
        except Exception as e:
            self.logger.warn(f"Smoke test error (non-fatal): {e}")
```

### 4E. Sửa `types/build.ts` — Update TypeScript types

> ⚠️ PATCH P5: PhaseId và PHASES cần thêm P6

```typescript
export type PhaseId = "p0" | "p1" | "p2" | "p3" | "p4" | "p5" | "p6";
// ⚠️ KHÔNG thêm "p55" — P55 là sub-step, không có phase riêng trên frontend

export const PHASES: Omit<PhaseInfo, "status" | "score" | "progress">[] = [
  { id: "p0", name: "Baseline", icon: "📖", tool: "Seekers" },
  { id: "p1", name: "Audit", icon: "🔍", tool: "Claude" },
  { id: "p2", name: "Extract", icon: "⚛️", tool: "Claude" },
  { id: "p3", name: "Deduplicate", icon: "🔄", tool: "Claude+Seekers" },
  { id: "p4", name: "Verify", icon: "✅", tool: "Seekers+Claude" },
  { id: "p5", name: "Architect", icon: "📦", tool: "Claude+Seekers" },
  { id: "p6", name: "Optimize", icon: "🎯", tool: "Claude" },
];
```

### 4F. Sửa `components/build/phase-stepper.tsx` — Thêm P6 color

> ⚠️ PATCH P5: PHASE_COLORS cũng cần P6

```typescript
const PHASE_COLORS: Record<string, string> = {
  p0: "text-indigo-400 border-indigo-400",
  p1: "text-amber-400 border-amber-400",
  p2: "text-emerald-400 border-emerald-400",
  p3: "text-purple-400 border-purple-400",
  p4: "text-red-400 border-red-400",
  p5: "text-cyan-400 border-cyan-400",
  p6: "text-rose-400 border-rose-400",
};
```

### 4G. Sửa `hooks/use-build-stream.ts` — Thêm P6 vào INITIAL_PHASES

> ⚠️ PATCH P5: INITIAL_PHASES là hardcoded riêng biệt với PHASES — PHẢI sync
> Frontend có 2 danh sách riêng: PHASES (metadata) và INITIAL_PHASES (state tracking).
> Nếu CHỈ sửa PHASES mà không sửa INITIAL_PHASES → P6 invisible trên stepper.

```typescript
const INITIAL_PHASES: PhaseState[] = [
  { id: "p0", status: "pending", progress: 0, score: null, name: "Baseline" },
  { id: "p1", status: "pending", progress: 0, score: null, name: "Audit" },
  { id: "p2", status: "pending", progress: 0, score: null, name: "Extract" },
  { id: "p3", status: "pending", progress: 0, score: null, name: "Deduplicate" },
  { id: "p4", status: "pending", progress: 0, score: null, name: "Verify" },
  { id: "p5", status: "pending", progress: 0, score: null, name: "Architect" },
  { id: "p6", status: "pending", progress: 0, score: null, name: "Optimize" },
];
// ⚠️ KHÔNG thêm P55 — P55 logs dưới phase="p5", không có UI riêng
```

**LƯU Ý về parseInt logic:** Frontend dùng `parseInt(phase.replace("p",""))` ở 3 nơi (lines 79, 111, 112).
Với Option A (chỉ p0-p6, không có p55), parseInt hoạt động đúng vì array index = parseInt value:
`p0(0), p1(1), p2(2), p3(3), p4(4), p5(5), p6(6)` — tất cả khớp.
**KHÔNG cần refactor parseInt cho Sprint 2.** Xem Sprint 3 TODO cho PHASE_ORDER refactor.

### 4H. Sửa `pipeline/core/logger.py` — Assert guard cho sub-phases

> ⚠️ PATCH P6: Nếu ai vô tình gọi phase_start("p55"), DB sẽ chứa current_phase="p55"
> → browser reconnect → parseInt("55")=55 → stepper hỏng.
> Assert guard chặn bug này ở dev/test time.

Thêm guard vào `phase_start` (warn + return thay vì assert — assert bị disable khi `python -O`):
```python
def phase_start(self, phase: str, name: str, tool: str = "Claude") -> None:
    # ⚠️ Sub-phase IDs (e.g. "p55") must NOT use phase_start — breaks frontend parseInt.
    # Main phases: p0-p9 (≤2 chars). Sub-phases: p55, p5a (3+ chars) → use logger.info() only.
    if len(phase) > 2:
        self.warn(f"Skipping phase_start for sub-phase '{phase}' — use info() instead")
        return  # Silent skip, don't crash production
    self._emit({"event": "phase", "phase": phase, "name": name,
                 "status": "running", "progress": 0})
    self.info(f"▶ Starting {name} phase ({tool})...", phase=phase)
```

### Validation Task 4
```bash
# Python
cd pipeline && python -m pytest tests/ -x

# Verify PyYAML extract on production data:
python -c "
import yaml, re
with open('output/fb-ads-meta/SKILL.md') as f:
    content = f.read()
fm = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
data = yaml.safe_load(fm.group(1))
desc = data['description']
print(f'Description: {desc[:80]}...')
print(f'Length: {len(desc)} chars')
assert len(desc) > 50, 'PyYAML extract failed!'
print('✅ PyYAML extract OK')
"

# Frontend
npm run build  # TypeScript compile check — verifies PhaseId union
```

---

## TASK 5: P5.5 Smoke Test Phase (Idea #4) — OPTION A: INLINE SUB-STEP
**File mới**: `pipeline/phases/p55_smoke_test.py`
**File sửa**: `pipeline/orchestrator/runner.py` (đã sửa trong Task 4D)
**Thời gian**: 1-2 ngày

> ⚠️ PATCH P9: P55 là sub-step, KHÔNG phải phase riêng.
> KHÔNG thêm P55 vào Python PHASES list.
> KHÔNG thêm P55 vào TypeScript PHASES/INITIAL_PHASES.
> KHÔNG gọi logger.phase_start() hay logger.phase_complete().
> Runner gọi P55 INLINE sau P5 (đã viết trong Task 4D).

### Tạo `pipeline/phases/p55_smoke_test.py`

```python
"""Phase 5.5 — Smoke Test: Validate built skill works correctly before optimization.

Generates 3-5 realistic test prompts from knowledge atoms,
runs them with SKILL.md in system context,
and checks if responses use the skill's knowledge accurately.

This is a NON-BLOCKING sub-step: failures produce warnings, not pipeline stops.

⚠️ CRITICAL: KHÔNG dùng logger.phase_start("p55", ...) 
P55 là sub-step của P5, chỉ dùng logger.info()/logger.warn() với phase="p5".
Nếu emit phase event → frontend parseInt("p55")=55 → stepper hỏng.
Xem Task 4H assert guard.
"""

import os
import time
import json
from typing import Optional

from ..core.types import BuildConfig, PhaseResult
from ..core.logger import PipelineLogger
from ..core.errors import PhaseError
from ..core.utils import read_json, write_json
from ..clients.claude_client import ClaudeClient
from ..seekers.cache import SeekersCache
from ..seekers.lookup import SeekersLookup

SMOKE_TEST_COUNT = 5
PASS_THRESHOLD = 0.6

GENERATE_PROMPTS_SYSTEM = """\
You are creating realistic test prompts to validate an AI knowledge skill.

Generate {count} test prompts that a real user would ask. Each prompt should:
1. Be specific enough that a good answer REQUIRES the skill's knowledge
2. Cover different knowledge pillars/categories
3. Vary in complexity (1 simple, 2 medium, 2 complex)
4. Use natural language (not "test the skill about X")

For each prompt, write 2-3 KEY FACTS that a correct answer must include.
OUTPUT: JSON array only.\
"""

GENERATE_PROMPTS_USER = """\
Generate {count} test prompts for this skill:

**Skill name:** {name}
**Domain:** {domain}

**Sample knowledge atoms:**
{sample_atoms}

Return JSON array:
[
  {{
    "prompt": "A realistic user question",
    "expected_facts": ["Fact the answer must include", "Another required fact"],
    "category": "Which knowledge pillar this tests",
    "complexity": "simple|medium|complex"
  }}
]
"""

GRADE_RESPONSE_SYSTEM = """\
You are grading an AI assistant's response to check if it correctly used knowledge from a skill.
Check if the response contains the expected facts. Be generous — facts don't need to be verbatim.
OUTPUT: JSON only.\
"""

GRADE_RESPONSE_USER = """\
**Question:** {prompt}
**Expected facts:** {expected_facts}
**AI response:** {response}

{{
  "results": [
    {{"fact": "expected fact", "present": true, "evidence": "where in response"}}
  ],
  "overall_pass": true,
  "score": 0.8,
  "notes": "Brief assessment"
}}
"""


def run_p55(
    config: BuildConfig, claude: Optional[ClaudeClient],
    cache: SeekersCache, lookup: SeekersLookup, logger: PipelineLogger,
) -> PhaseResult:
    """Run P5.5 Smoke Test (non-blocking sub-step).
    
    ⚠️ Logs under phase="p5" — NEVER use phase_start/phase_complete with "p55".
    """
    phase = "p5"  # Sub-step — log under p5, NOT p55
    started = time.time()
    logger.info("🧪 Running Smoke Test...", phase=phase)

    if not claude:
        logger.warn("Smoke test skipped — no Claude client", phase=phase)
        return PhaseResult(phase_id="p55", status="skipped")

    # Read model hint
    use_light = config.phase_model_hints.get("p55", True)

    try:
        skill_path = os.path.join(config.output_dir, "SKILL.md")
        if not os.path.exists(skill_path):
            return PhaseResult(phase_id="p55", status="skipped", error_message="SKILL.md not found")
        with open(skill_path, 'r', encoding='utf-8') as f:
            skill_content = f.read()

        # Load atoms for context
        sample_atoms = "Not available"
        for atoms_file in ["atoms_verified.json", "atoms_deduplicated.json"]:
            atoms_path = os.path.join(config.output_dir, atoms_file)
            if os.path.exists(atoms_path):
                data = read_json(atoms_path)
                atoms = data.get("atoms", [])[:10]
                sample_atoms = json.dumps(
                    [{"title": a.get("title", ""), "content": a.get("content", "")[:200]} for a in atoms],
                    ensure_ascii=False, indent=2,
                )
                break

        # Step 1: Generate test prompts
        logger.info("Generating smoke test prompts...", phase=phase)
        test_prompts = claude.call_json(
            system=GENERATE_PROMPTS_SYSTEM.format(count=SMOKE_TEST_COUNT),
            user=GENERATE_PROMPTS_USER.format(
                count=SMOKE_TEST_COUNT, name=config.name,
                domain=config.domain, sample_atoms=sample_atoms,
            ),
            max_tokens=2048, phase=phase, use_light_model=use_light,
        )
        if isinstance(test_prompts, dict):
            test_prompts = test_prompts.get("prompts", test_prompts.get("tests", []))
        if not isinstance(test_prompts, list) or not test_prompts:
            logger.warn("Could not generate test prompts — skipping", phase=phase)
            return PhaseResult(phase_id="p55", status="skipped")

        # Step 2: Run and grade each test
        results = []
        for i, test in enumerate(test_prompts[:SMOKE_TEST_COUNT]):
            prompt = test.get("prompt", "")
            expected = test.get("expected_facts", [])
            if not prompt:
                continue
            logger.info(f"  Test {i+1}/{min(len(test_prompts), SMOKE_TEST_COUNT)}: {prompt[:60]}...", phase=phase)

            response = claude.call(
                system=f"You have access to this knowledge skill:\n\n{skill_content[:3000]}",
                user=prompt, max_tokens=1024, phase=phase,
            )
            grade = claude.call_json(
                system=GRADE_RESPONSE_SYSTEM,
                user=GRADE_RESPONSE_USER.format(
                    prompt=prompt,
                    expected_facts=json.dumps(expected, ensure_ascii=False),
                    response=response[:2000],
                ),
                max_tokens=1024, phase=phase, use_light_model=True,
            )
            passed = grade.get("overall_pass", False)
            score = grade.get("score", 0)
            results.append({
                "prompt": prompt, "expected_facts": expected,
                "response_preview": response[:300],
                "passed": passed, "score": score,
                "grade_notes": grade.get("notes", ""),
            })
            logger.info(f"  {'✅' if passed else '❌'} Score: {score:.0%}", phase=phase)

        # Step 3: Overall result
        pass_count = sum(1 for r in results if r["passed"])
        total = len(results)
        overall_score = pass_count / total if total > 0 else 0

        report = {
            "pass_count": pass_count, "total": total,
            "score": overall_score, "passed": overall_score >= PASS_THRESHOLD,
            "threshold": PASS_THRESHOLD, "results": results,
        }
        report_path = os.path.join(config.output_dir, "smoke_test_report.json")
        write_json(report, report_path)

        emoji = "✅" if overall_score >= PASS_THRESHOLD else "⚠️"
        logger.info(f"{emoji} Smoke Test: {pass_count}/{total} passed ({overall_score:.0%})", phase=phase)

        if overall_score < PASS_THRESHOLD:
            logger.warn("Smoke test below threshold — skill may need manual review", phase=phase)

        return PhaseResult(
            phase_id="p55", status="done",
            duration_seconds=round(time.time() - started, 1),
            quality_score=round(overall_score * 100, 1),
            output_files=[report_path],
            metrics={"pass_count": pass_count, "total": total, "overall_pass": overall_score >= PASS_THRESHOLD},
        )

    except Exception as e:
        logger.warn(f"Smoke test error (non-fatal): {e}", phase=phase)
        return PhaseResult(phase_id="p55", status="skipped", error_message=str(e))
```

### Validation Task 5
```bash
cd pipeline && python -m pytest tests/ -x
python -c "from pipeline.phases.p55_smoke_test import run_p55; print('Import OK')"
```

---
## ═══════════════════════════════════════════════════════════
## SPRINT 3: QUALITY & UI (TUẦN 3) — Tasks 6, 8, 9, 11
## ═══════════════════════════════════════════════════════════

## TASK 6: Update Tests
**File**: `pipeline/tests/test_phases.py`
**Thời gian**: 0.5 ngày

Thêm test classes cho P6, P5.5, Progressive Disclosure, Multi-Model:

```python
import pytest

class TestP6Optimize:
    def test_extract_description_double_quoted(self):
        from pipeline.phases.p6_optimize import _extract_description
        md = '---\nname: test\ndescription: "Use this for testing"\n---\n# Test'
        assert _extract_description(md) == "Use this for testing"

    def test_extract_description_unquoted(self):
        from pipeline.phases.p6_optimize import _extract_description
        md = '---\nname: test\ndescription: Use this for testing\n---\n# Test'
        assert _extract_description(md) == "Use this for testing"

    def test_replace_description(self):
        from pipeline.phases.p6_optimize import _replace_description
        md = '---\nname: test\ndescription: "old desc"\n---\n# Test'
        result = _replace_description(md, "new desc here")
        assert "new desc here" in result
        assert "old desc" not in result

    def test_split_eval_set_stratified(self):
        from pipeline.phases.p6_optimize import _split_eval_set
        evals = [{"query": f"q{i}", "should_trigger": i < 10} for i in range(20)]
        train, test = _split_eval_set(evals, holdout=0.4)
        assert any(e["should_trigger"] for e in train)
        assert any(not e["should_trigger"] for e in train)
        assert any(e["should_trigger"] for e in test)

    def test_calc_score(self):
        from pipeline.phases.p6_optimize import _calc_score
        assert _calc_score([{"pass": True}, {"pass": True}, {"pass": False}]) == pytest.approx(2/3)
        assert _calc_score([]) == 0.0


class TestP55SmokeTest:
    def test_import(self):
        from pipeline.phases.p55_smoke_test import run_p55
        assert callable(run_p55)

    def test_skips_without_claude(self, tmp_path):
        from pipeline.phases.p55_smoke_test import run_p55
        from pipeline.core.types import BuildConfig
        from pipeline.core.logger import PipelineLogger
        config = BuildConfig(name="test", domain="test", output_dir=str(tmp_path))
        result = run_p55(config, None, None, None, PipelineLogger())
        assert result.status == "skipped"


class TestProgressiveDisclosure:
    def test_description_too_short(self):
        from pipeline.phases.p5_build import _enforce_progressive_disclosure
        from pipeline.core.logger import PipelineLogger
        _, warnings = _enforce_progressive_disclosure("# Test", "Short", {}, PipelineLogger())
        assert any("undertrigger" in w.lower() or "too short" in w.lower() for w in warnings)

    def test_description_ok(self):
        from pipeline.phases.p5_build import _enforce_progressive_disclosure
        from pipeline.core.logger import PipelineLogger
        desc = " ".join(["word"] * 120)
        _, warnings = _enforce_progressive_disclosure("# Test", desc, {}, PipelineLogger())
        desc_warnings = [w for w in warnings if "escription" in w]
        assert len(desc_warnings) == 0


class TestMultiModelStrategy:
    def test_phase_model_map_structure(self):
        from pipeline.core.types import PHASE_MODEL_MAP
        for tier in ["draft", "standard", "premium"]:
            assert tier in PHASE_MODEL_MAP
            assert "p1" in PHASE_MODEL_MAP[tier]
            assert "p5" in PHASE_MODEL_MAP[tier]

    def test_draft_uses_light_for_p1(self):
        from pipeline.core.types import PHASE_MODEL_MAP
        assert PHASE_MODEL_MAP["draft"]["p1"] is True

    def test_premium_uses_full_for_all(self):
        from pipeline.core.types import PHASE_MODEL_MAP
        for phase_id, use_light in PHASE_MODEL_MAP["premium"].items():
            assert use_light is False, f"Premium should use full model for {phase_id}"
```

---

## TASK 8: Eval Query Generator UI (Idea #6)
**Files mới**:
- `components/build/eval-trigger-panel.tsx`
- `app/api/builds/[id]/eval-trigger/route.ts`
**Files sửa**:
- `app/build/[id]/page.tsx` (thêm tab)
**Thời gian**: 2-3 ngày

### 8A. Tạo API endpoint `app/api/builds/[id]/eval-trigger/route.ts`

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
import path from "path";
import fs from "fs";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build || !build.output_path) {
    return NextResponse.json({ error: "Build not found" }, { status: 404 });
  }

  // Read P6 optimization report if exists
  const reportPath = path.join(build.output_path, "p6_optimization_report.json");
  if (!fs.existsSync(reportPath)) {
    return NextResponse.json({ eval_set: [], report: null });
  }

  const report = JSON.parse(fs.readFileSync(reportPath, "utf-8"));
  return NextResponse.json({
    eval_set: report.eval_set || [],
    report: {
      best_train_score: report.best_train_score,
      best_test_score: report.best_test_score,
      iterations: report.iterations,
      original_description: report.original_description || "",
      best_description: report.best_description || "",
      history: report.history || [],
    },
  });
}
```

### 8B. Tạo `components/build/eval-trigger-panel.tsx`

```tsx
"use client";

import { useEffect, useState } from "react";
import { Check, X, Loader2, Target, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface EvalQuery {
  query: string;
  should_trigger: boolean;
  reasoning?: string;
  trigger_rate?: number;
  pass?: boolean;
}

interface OptReport {
  best_train_score: number;
  best_test_score: number;
  iterations: number;
  original_description: string;
  best_description: string;
  history: { iteration: number; train_score: number; test_score: number; description: string }[];
}

export function EvalTriggerPanel({ buildId }: { buildId: string }) {
  const [evalSet, setEvalSet] = useState<EvalQuery[]>([]);
  const [report, setReport] = useState<OptReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/builds/${buildId}/eval-trigger`)
      .then((r) => r.json())
      .then((data) => {
        setEvalSet(data.eval_set || []);
        setReport(data.report || null);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [buildId]);

  if (loading) return <Loader2 className="w-5 h-5 animate-spin text-muted-foreground mx-auto my-8" />;
  if (!report) return <p className="text-sm text-muted-foreground text-center py-8">P6 Optimization not yet run for this build.</p>;

  const shouldTrigger = evalSet.filter((e) => e.should_trigger);
  const shouldNot = evalSet.filter((e) => !e.should_trigger);

  return (
    <div className="space-y-6">
      {/* Score Summary */}
      <div className="grid grid-cols-3 gap-3">
        <ScoreCard label="Train Score" value={report.best_train_score} />
        <ScoreCard label="Test Score" value={report.best_test_score} />
        <div className="p-3 rounded-lg bg-card border border-border text-center">
          <p className="text-xs text-muted-foreground">Iterations</p>
          <p className="text-lg font-bold text-foreground">{report.iterations}</p>
        </div>
      </div>

      {/* Description Before/After */}
      {report.original_description && report.original_description !== report.best_description && (
        <div className="p-4 rounded-xl bg-card border border-border space-y-3">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Description Optimization
          </h4>
          <div className="space-y-2">
            <div>
              <p className="text-xs text-red-400 mb-1">Before:</p>
              <p className="text-xs text-muted-foreground bg-muted/30 p-2 rounded">{report.original_description}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-400 mb-1">After:</p>
              <p className="text-xs text-foreground bg-muted/30 p-2 rounded">{report.best_description}</p>
            </div>
          </div>
        </div>
      )}

      {/* Eval Queries */}
      <div className="p-4 rounded-xl bg-card border border-border">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
          <Target className="w-3.5 h-3.5" /> Should Trigger ({shouldTrigger.length})
        </h4>
        <div className="space-y-1">
          {shouldTrigger.map((q, i) => (
            <QueryRow key={i} query={q} />
          ))}
        </div>
      </div>

      <div className="p-4 rounded-xl bg-card border border-border">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
          <Zap className="w-3.5 h-3.5" /> Should NOT Trigger ({shouldNot.length})
        </h4>
        <div className="space-y-1">
          {shouldNot.map((q, i) => (
            <QueryRow key={i} query={q} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div className="p-3 rounded-lg bg-card border border-border text-center">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("text-lg font-bold", pct >= 80 ? "text-emerald-400" : pct >= 60 ? "text-amber-400" : "text-red-400")}>
        {pct}%
      </p>
    </div>
  );
}

function QueryRow({ query }: { query: EvalQuery }) {
  const hasResult = query.pass !== undefined;
  return (
    <div className="flex items-start gap-2 py-1.5">
      {hasResult ? (
        query.pass ? <Check className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" /> : <X className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
      ) : (
        <div className="w-4 h-4 rounded-full border border-border mt-0.5 shrink-0" />
      )}
      <p className="text-xs text-muted-foreground">{query.query}</p>
    </div>
  );
}
```

### 8C. Integration vào `app/build/[id]/page.tsx`

Tìm nơi tabs được render (Logs, Quality, Preview...). Thêm tab mới:

```tsx
import { EvalTriggerPanel } from "@/components/build/eval-trigger-panel";

// In the tabs section, add:
// Tab header:
<button onClick={() => setTab("eval")} className={...}>🎯 Triggering</button>

// Tab content:
{tab === "eval" && <EvalTriggerPanel buildId={build.id} />}
```

---

## TASK 9: Build History & A/B Compare (Idea #7)
**Files mới**:
- `app/api/builds/compare/route.ts`
- `components/build/build-compare.tsx`
- `app/compare/page.tsx`
**Files sửa**:
- `components/layout/sidebar.tsx` (thêm nav link)
**Thời gian**: 2-3 ngày

### 9A. Tạo API `app/api/builds/compare/route.ts`

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
import path from "path";
import fs from "fs";

export async function GET(req: NextRequest) {
  const a = req.nextUrl.searchParams.get("a");
  const b = req.nextUrl.searchParams.get("b");
  if (!a || !b) return NextResponse.json({ error: "Need ?a=...&b=..." }, { status: 400 });

  const buildA = getBuild(a);
  const buildB = getBuild(b);
  if (!buildA || !buildB) return NextResponse.json({ error: "Build not found" }, { status: 404 });

  const loadReport = (build: typeof buildA) => {
    if (!build?.output_path) return null;
    const files: Record<string, unknown> = {};
    for (const name of ["p6_optimization_report.json", "smoke_test_report.json"]) {
      const p = path.join(build.output_path, name);
      if (fs.existsSync(p)) files[name] = JSON.parse(fs.readFileSync(p, "utf-8"));
    }
    // Read SKILL.md description
    // ⚠️ PATCH: Read from P6 report first (regex truncates yaml.dump multi-line output)
    const p6ReportPath = path.join(build.output_path, "p6_optimization_report.json");
    if (fs.existsSync(p6ReportPath)) {
      try {
        const p6Report = JSON.parse(fs.readFileSync(p6ReportPath, "utf-8"));
        files["description"] = p6Report.best_description || "";
      } catch { files["description"] = ""; }
    }
    // Fallback for pre-v2 builds without P6 report
    if (!files["description"]) {
      const skillPath = path.join(build.output_path, "SKILL.md");
      if (fs.existsSync(skillPath)) {
        const content = fs.readFileSync(skillPath, "utf-8");
        const match = content.match(/^description:\s*"?(.*?)"?\s*$/m);
        files["description"] = match?.[1] || "";
      }
    }
    return files;
  };

  return NextResponse.json({
    a: { ...buildA, reports: loadReport(buildA) },
    b: { ...buildB, reports: loadReport(buildB) },
  });
}
```

### 9B. Tạo `components/build/build-compare.tsx`

```tsx
"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { cn, formatCost } from "@/lib/utils";
import type { Build } from "@/types/build";

interface CompareData {
  a: Build & { reports: Record<string, unknown> | null };
  b: Build & { reports: Record<string, unknown> | null };
}

export function BuildCompare({ idA, idB }: { idA: string; idB: string }) {
  const [data, setData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/builds/compare?a=${idA}&b=${idB}`)
      .then((r) => r.json())
      .then((d) => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [idA, idB]);

  if (loading) return <Loader2 className="w-5 h-5 animate-spin mx-auto my-8" />;
  if (!data) return <p className="text-sm text-muted-foreground">Could not load comparison.</p>;

  const rows = [
    { label: "Quality Score", a: data.a.quality_score, b: data.b.quality_score, higher: "better" },
    { label: "Atoms Verified", a: data.a.atoms_verified, b: data.b.atoms_verified, higher: "better" },
    { label: "API Cost", a: data.a.api_cost_usd, b: data.b.api_cost_usd, higher: "worse" },
    { label: "Tokens Used", a: data.a.tokens_used, b: data.b.tokens_used, higher: "worse" },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="grid grid-cols-3 gap-4 text-center">
        <div />
        <div className="p-3 rounded-lg bg-card border border-border">
          <p className="text-sm font-semibold">{data.a.name}</p>
          <p className="text-xs text-muted-foreground">{data.a.domain}</p>
        </div>
        <div className="p-3 rounded-lg bg-card border border-border">
          <p className="text-sm font-semibold">{data.b.name}</p>
          <p className="text-xs text-muted-foreground">{data.b.domain}</p>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="rounded-xl border border-border overflow-hidden">
        {rows.map((row, i) => (
          <div key={i} className={cn("grid grid-cols-3 gap-4 p-3 text-sm", i % 2 === 0 ? "bg-card" : "bg-muted/20")}>
            <span className="text-muted-foreground">{row.label}</span>
            <span className={cn("text-center font-mono",
              row.a != null && row.b != null && (
                row.higher === "better" ? (row.a > row.b ? "text-emerald-400" : row.a < row.b ? "text-red-400" : "") :
                (row.a < row.b ? "text-emerald-400" : row.a > row.b ? "text-red-400" : "")
              )
            )}>{row.a ?? "—"}</span>
            <span className={cn("text-center font-mono",
              row.a != null && row.b != null && (
                row.higher === "better" ? (row.b > row.a ? "text-emerald-400" : row.b < row.a ? "text-red-400" : "") :
                (row.b < row.a ? "text-emerald-400" : row.b > row.a ? "text-red-400" : "")
              )
            )}>{row.b ?? "—"}</span>
          </div>
        ))}
      </div>

      {/* Description Comparison */}
      <div className="p-4 rounded-xl bg-card border border-border space-y-2">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase">Description Comparison</h4>
        <div className="grid grid-cols-2 gap-3">
          <p className="text-xs text-muted-foreground bg-muted/30 p-2 rounded">
            {(data.a.reports?.description as string) || "N/A"}
          </p>
          <p className="text-xs text-muted-foreground bg-muted/30 p-2 rounded">
            {(data.b.reports?.description as string) || "N/A"}
          </p>
        </div>
      </div>
    </div>
  );
}
```

### 9C. Tạo page `app/compare/page.tsx`

```tsx
"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BuildCompare } from "@/components/build/build-compare";
import type { Build } from "@/types/build";

export default function ComparePage() {
  const searchParams = useSearchParams();
  const a = searchParams.get("a");
  const b = searchParams.get("b");
  const [builds, setBuilds] = useState<Build[]>([]);
  const [selectedA, setSelectedA] = useState(a || "");
  const [selectedB, setSelectedB] = useState(b || "");

  useEffect(() => {
    fetch("/api/builds?status=completed").then(r => r.json()).then(setBuilds);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Compare Builds</h1>
      <div className="grid grid-cols-2 gap-4">
        <select value={selectedA} onChange={e => setSelectedA(e.target.value)} className="bg-card border border-border rounded-lg p-2 text-sm">
          <option value="">Select Build A...</option>
          {builds.map(b => <option key={b.id} value={b.id}>{b.name} ({b.domain})</option>)}
        </select>
        <select value={selectedB} onChange={e => setSelectedB(e.target.value)} className="bg-card border border-border rounded-lg p-2 text-sm">
          <option value="">Select Build B...</option>
          {builds.map(b => <option key={b.id} value={b.id}>{b.name} ({b.domain})</option>)}
        </select>
      </div>
      {selectedA && selectedB && <BuildCompare idA={selectedA} idB={selectedB} />}
    </div>
  );
}
```

### 9D. Sửa `components/layout/sidebar.tsx` — thêm Compare nav link

Tìm nav items array, thêm:
```tsx
{ href: "/compare", icon: GitCompareArrows, label: "Compare" },
```
Import: `import { GitCompareArrows } from "lucide-react";`

---

## TASK 10: Script Auto-Bundler (Idea #8)
**File sửa**: `pipeline/phases/p5_build.py`
**File mới**: `pipeline/prompts/p5_script_prompts.py`
**Thời gian**: 1-2 ngày

### 10A. Tạo `pipeline/prompts/p5_script_prompts.py`

```python
"""P5 Script Bundler — Auto-generate helper scripts based on domain patterns."""

P5_SCRIPT_SYSTEM = """\
You are a utility script generator. Based on the knowledge domain and atoms, determine if 
commonly-needed utility scripts would help users of this skill.

COMMON PATTERNS:
- Marketing domains → calculators (ROAS, CPM, CPA, LTV, CAC)
- Technical domains → template generators, config scaffolders
- Process domains → checklists, audit scripts
- Data domains → validators, format converters

Only generate scripts if they would be genuinely useful. Not every skill needs them.

OUTPUT: JSON with "scripts" array. Each script has name, description, language, and code.
If no scripts are needed, return {"scripts": [], "reason": "..."}.\
"""

P5_SCRIPT_USER = """\
Analyze if this skill would benefit from bundled utility scripts.

**Skill name:** {name}
**Domain:** {domain}
**Knowledge topics:** {topics}
**Sample atoms (for context):** {sample_atoms}

Return JSON:
{{
  "scripts": [
    {{
      "name": "calculator.py",
      "description": "ROAS and CPM calculator for ad campaigns",
      "language": "python",
      "code": "# Full script code here"
    }}
  ],
  "reason": "Why these scripts were or weren't generated"
}}
"""
```

### 10B. Add bundler function to `p5_build.py`

Thêm function vào cuối file (trước `_generate_fallback_skill`):

```python
from ..prompts.p5_script_prompts import P5_SCRIPT_SYSTEM, P5_SCRIPT_USER

def _maybe_bundle_scripts(
    config: BuildConfig, claude: ClaudeClient,
    atoms: list, topics: str, logger: PipelineLogger,
) -> list[dict]:
    """Auto-generate helper scripts if domain patterns suggest they'd be useful.
    
    Returns list of {name, description, code} dicts.
    Only runs for standard/premium tiers.
    """
    if config.quality_tier == "draft":
        return []

    sample = json.dumps(
        [{"title": a.get("title", ""), "content": a.get("content", "")[:150]}
         for a in atoms[:8]],
        ensure_ascii=False,
    )

    try:
        result = claude.call_json(
            system=P5_SCRIPT_SYSTEM,
            user=P5_SCRIPT_USER.format(
                name=config.name, domain=config.domain,
                topics=topics, sample_atoms=sample,
            ),
            max_tokens=4096, phase="p5", use_light_model=True,
        )
        scripts = result.get("scripts", [])
        if scripts:
            logger.info(f"📦 Auto-bundled {len(scripts)} helper scripts", phase="p5")
            for s in scripts:
                logger.info(f"  → {s.get('name', '?')}: {s.get('description', '')[:60]}", phase="p5")
        return scripts
    except Exception as e:
        logger.warn(f"Script bundling failed (non-fatal): {e}", phase="p5")
        return []
```

### Integration in `run_p5()`:
After packaging knowledge files, before creating zip:
```python
scripts = _maybe_bundle_scripts(config, claude, build_atoms, topics_str, logger)
for script in scripts:
    script_path = os.path.join(config.output_dir, "scripts", script["name"])
    os.makedirs(os.path.dirname(script_path), exist_ok=True)
    write_file(script_path, script["code"])
```

---

## TASK 11: Quality Report 2.0 (Idea #9)
**File sửa**: `components/build/quality-report.tsx`
**Thời gian**: 1-2 ngày

### Yêu cầu
Upgrade quality report component to show smoke test + optimization results.

### Sửa `components/build/quality-report.tsx`

Thêm sections cho smoke test và P6 optimization SAU existing phase scores:

```tsx
// Add to imports:
import { useEffect, useState } from "react";
import { CheckCircle, XCircle, Target, ArrowUpRight } from "lucide-react";

// Add new sections inside the component, after Phase Scores:

// Fetch smoke test + P6 reports
const [smokeReport, setSmokeReport] = useState<any>(null);
const [optReport, setOptReport] = useState<any>(null);

useEffect(() => {
  if (!build.output_path) return;
  // Smoke test
  fetch(`/api/builds/${build.id}/reports?file=smoke_test_report.json`)
    .then(r => r.ok ? r.json() : null).then(setSmokeReport).catch(() => {});
  // P6 optimization  
  fetch(`/api/builds/${build.id}/reports?file=p6_optimization_report.json`)
    .then(r => r.ok ? r.json() : null).then(setOptReport).catch(() => {});
}, [build.id, build.output_path]);

// Render sections:

{/* Smoke Test Results */}
{smokeReport && (
  <div className="p-4 rounded-xl bg-card border border-border">
    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
      🧪 Smoke Test — {smokeReport.pass_count}/{smokeReport.total} passed
    </h4>
    <div className="space-y-2">
      {smokeReport.results?.map((r: any, i: number) => (
        <div key={i} className="flex items-start gap-2">
          {r.passed ? <CheckCircle className="w-4 h-4 text-emerald-400 mt-0.5" /> : <XCircle className="w-4 h-4 text-red-400 mt-0.5" />}
          <div>
            <p className="text-xs text-foreground">{r.prompt}</p>
            <p className="text-xs text-muted-foreground">{r.grade_notes}</p>
          </div>
        </div>
      ))}
    </div>
  </div>
)}

{/* P6 Optimization Results */}
{optReport && (
  <div className="p-4 rounded-xl bg-card border border-border">
    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 flex items-center gap-2">
      <Target className="w-3.5 h-3.5" /> Description Optimization
    </h4>
    <div className="grid grid-cols-3 gap-3 mb-3">
      <div className="text-center">
        <p className="text-xs text-muted-foreground">Train</p>
        <p className="text-lg font-bold text-emerald-400">{Math.round(optReport.best_train_score * 100)}%</p>
      </div>
      <div className="text-center">
        <p className="text-xs text-muted-foreground">Test</p>
        <p className="text-lg font-bold text-cyan-400">{Math.round(optReport.best_test_score * 100)}%</p>
      </div>
      <div className="text-center">
        <p className="text-xs text-muted-foreground">Iterations</p>
        <p className="text-lg font-bold text-foreground">{optReport.iterations}</p>
      </div>
    </div>
    {optReport.history?.length > 1 && (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <ArrowUpRight className="w-3 h-3 text-emerald-400" />
        Improved from {Math.round(optReport.history[0].test_score * 100)}% to {Math.round(optReport.best_test_score * 100)}%
      </div>
    )}
  </div>
)}
```

### Thêm API endpoint `app/api/builds/[id]/reports/route.ts`

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
import path from "path";
import fs from "fs";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const file = req.nextUrl.searchParams.get("file");
  if (!file) return NextResponse.json({ error: "file param required" }, { status: 400 });
  
  // Sanitize filename
  const safeName = path.basename(file);
  if (!safeName.endsWith(".json")) return NextResponse.json({ error: "JSON only" }, { status: 400 });

  const build = getBuild(id);
  if (!build?.output_path) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const filePath = path.join(build.output_path, safeName);
  if (!fs.existsSync(filePath)) return NextResponse.json(null, { status: 404 });

  return NextResponse.json(JSON.parse(fs.readFileSync(filePath, "utf-8")));
}
```

---


## TASK 14 (BONUS): PHASE_ORDER Refactor — Sprint 3 TODO
**File**: `hooks/use-build-stream.ts`
**Thời gian**: 10 phút
**Priority**: Low — defensive coding, future-proof

> Hiện tại parseInt logic works vì p0-p6 liên tục (index = parseInt value).
> Nếu tương lai thêm phase nào không tuần tự → hỏng.
> Refactor này auto-derive order từ INITIAL_PHASES → zero maintenance.

```typescript
// Thêm vào use-build-stream.ts SAU INITIAL_PHASES:
const PHASE_ORDER: Record<string, number> =
  Object.fromEntries(INITIAL_PHASES.map((p, i) => [p.id, i]));
const phaseRank = (id: string) => PHASE_ORDER[id] ?? -1;

// Thay 3 chỗ parseInt:

// Line 79 ("state" handler):
const currentRank = phaseRank(data.current_phase);
setPhases((prev) =>
  prev.map((p) => {
    const thisRank = phaseRank(p.id);
    if (thisRank < currentRank) return { ...p, status: "done", progress: 100 };
    if (thisRank === currentRank)
      return { ...p, status: "running", progress: data.phase_progress || 0 };
    return p;
  })
);

// Lines 111-112 ("phase" handler):
const incomingRank = phaseRank(data.phase);
const thisRank = phaseRank(p.id);
if (thisRank < incomingRank && p.status !== "done") {
  return { ...p, status: "done", progress: 100 };
}
```

---
## ═══════════════════════════════════════════════════════════
## SPRINT 4: ADVANCED (TUẦN 4+) — Tasks 12, 13
## ═══════════════════════════════════════════════════════════

## TASK 12: Enhanced Skill Template Library (Idea #11)
**Files sửa**:
- `lib/db-schema.ts` (extend templates table)
- `app/templates/page.tsx` (rich UI)
- `app/api/templates/route.ts`
**File mới**:
- `pipeline/data/seed-templates/` (pre-optimized template data)
**Thời gian**: 2-3 ngày

### 12A. Extend templates table schema

Trong `lib/db-schema.ts`, thêm columns mới vào templates table (migration-safe):

```typescript
// Add after initializeSchema, as a migration:
db.exec(`
  -- Add optimized_description column (pre-tested description)
  ALTER TABLE templates ADD COLUMN optimized_description TEXT;
`).catch(() => {}); // Ignore if column already exists

db.exec(`
  -- Add eval_queries column (pre-built test queries as JSON array)
  ALTER TABLE templates ADD COLUMN eval_queries TEXT;
`).catch(() => {});

db.exec(`
  -- Add taxonomy column (domain categories as JSON) 
  ALTER TABLE templates ADD COLUMN taxonomy TEXT;
`).catch(() => {});

db.exec(`
  -- Add avg_quality column (average quality from builds using this template)
  ALTER TABLE templates ADD COLUMN avg_quality REAL;
`).catch(() => {});
```

NOTE: SQLite ALTER TABLE ADD COLUMN doesn't support IF NOT EXISTS. Use try-catch or check column existence first:
```typescript
const hasCol = db.prepare("PRAGMA table_info(templates)").all()
  .some((col: any) => col.name === "optimized_description");
if (!hasCol) {
  db.exec("ALTER TABLE templates ADD COLUMN optimized_description TEXT");
  db.exec("ALTER TABLE templates ADD COLUMN eval_queries TEXT");
  db.exec("ALTER TABLE templates ADD COLUMN taxonomy TEXT");
  db.exec("ALTER TABLE templates ADD COLUMN avg_quality REAL");
}
```

### 12B. Seed enhanced templates

Update the template seed data in `db-schema.ts` to include pre-optimized descriptions:

```typescript
// For the FB Ads template, add:
optimized_description: `Use this skill whenever the user asks about Facebook advertising, Meta Ads, 
campaign optimization, ROAS improvement, ad spend allocation, audience targeting, Facebook Pixel, 
Custom Audiences, Lookalike Audiences, ad creative testing, CPM/CPC/CPA optimization, or any 
question about running paid campaigns on Facebook/Instagram/Meta platforms. Also trigger when users 
mention declining ad performance, iOS tracking changes affecting ads, or budget allocation for 
social media advertising — even if they don't explicitly say 'Facebook Ads'. Do NOT use for organic 
social media, SEO, Google Ads, or non-advertising Meta features.`,
```

### 12C. Enrich template page UI

Update `app/templates/page.tsx` to show quality stats, description preview, and "Use" button:
```tsx
{/* Add to template card: */}
{tpl.avg_quality && (
  <div className="text-xs text-emerald-400">Avg Quality: {Math.round(tpl.avg_quality)}%</div>
)}
{tpl.optimized_description && (
  <p className="text-xs text-muted-foreground mt-2 line-clamp-3">
    📝 Pre-optimized description included
  </p>
)}
```

### 12D. When build uses template with optimized_description:

In `pipeline/phases/p5_build.py`, check if config has a pre-optimized description from template. If so, use it as the starting point for P6 instead of generating from scratch.

Add to BuildConfig in `types.py`:
```python
template_optimized_description: str = ""  # Pre-tested description from template
```

Pass this into P6 so it starts from a stronger baseline.

---

## TASK 13: Self-Improving Pipeline (Idea #12)
**Files mới**:
- `lib/feedback.ts`
- `app/api/builds/[id]/feedback/route.ts`
- `components/build/feedback-widget.tsx`
**Files sửa**:
- `lib/db-schema.ts` (add feedback table)
- `pipeline/prompts/p5_build_prompts.py` (inject lessons learned)
**Thời gian**: 2-3 ngày

### 13A. Add feedback table to `lib/db-schema.ts`

```typescript
db.exec(`
  CREATE TABLE IF NOT EXISTS build_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id    TEXT NOT NULL,
    domain      TEXT,
    rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    feedback    TEXT,
    issues      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_feedback_domain ON build_feedback(domain);
`);
```

### 13B. Create `lib/feedback.ts`

```typescript
import { getDb } from "./db";

export function submitFeedback(buildId: string, domain: string | null, rating: number, feedback: string, issues: string) {
  getDb().prepare(`
    INSERT INTO build_feedback (build_id, domain, rating, feedback, issues) VALUES (?, ?, ?, ?, ?)
  `).run(buildId, domain, rating, feedback, issues);
}

export function getDomainLessons(domain: string, limit: number = 5): string {
  const rows = getDb().prepare(`
    SELECT rating, feedback, issues FROM build_feedback 
    WHERE domain = ? AND feedback IS NOT NULL AND feedback != '' 
    ORDER BY created_at DESC LIMIT ?
  `).all(domain, limit) as { rating: number; feedback: string; issues: string }[];

  if (rows.length === 0) return "";

  const avgRating = rows.reduce((sum, r) => sum + r.rating, 0) / rows.length;
  const commonIssues = rows.filter(r => r.issues).map(r => r.issues).join("; ");

  return `LESSONS FROM PREVIOUS BUILDS (domain: ${domain}, avg rating: ${avgRating.toFixed(1)}/5):\n` +
    `Common issues: ${commonIssues || "None reported"}\n` +
    `User feedback: ${rows.map(r => `[${r.rating}★] ${r.feedback}`).join(" | ")}`;
}
```

### 13C. Create API `app/api/builds/[id]/feedback/route.ts`

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
import { submitFeedback } from "@/lib/feedback";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const body = await req.json();
  const { rating, feedback, issues } = body;
  if (!rating || rating < 1 || rating > 5) {
    return NextResponse.json({ error: "Rating 1-5 required" }, { status: 400 });
  }

  submitFeedback(id, build.domain, rating, feedback || "", issues || "");
  return NextResponse.json({ ok: true });
}
```

### 13D. Create `components/build/feedback-widget.tsx`

```tsx
"use client";

import { useState } from "react";
import { Star, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function FeedbackWidget({ buildId }: { buildId: string }) {
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [issues, setIssues] = useState<string[]>([]);
  const [submitted, setSubmitted] = useState(false);

  const issueOptions = [
    "Missing topics", "Inaccurate information", "Description too vague",
    "Too few atoms", "Redundant content", "Wrong language",
  ];

  const submit = async () => {
    await fetch(`/api/builds/${buildId}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating, feedback, issues: issues.join("; ") }),
    });
    setSubmitted(true);
  };

  if (submitted) return <p className="text-sm text-emerald-400 text-center py-4">✅ Thanks for your feedback!</p>;

  return (
    <div className="p-4 rounded-xl bg-card border border-border space-y-3">
      <h4 className="text-xs font-semibold text-muted-foreground uppercase">Rate this build</h4>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} onClick={() => setRating(n)}>
            <Star className={cn("w-6 h-6", n <= rating ? "text-amber-400 fill-amber-400" : "text-muted-foreground")} />
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {issueOptions.map((iss) => (
          <button key={iss} onClick={() => setIssues(prev => prev.includes(iss) ? prev.filter(i => i !== iss) : [...prev, iss])}
            className={cn("px-2 py-1 rounded-md text-xs border",
              issues.includes(iss) ? "bg-red-500/20 border-red-500/50 text-red-400" : "border-border text-muted-foreground"
            )}>
            {iss}
          </button>
        ))}
      </div>
      <textarea value={feedback} onChange={e => setFeedback(e.target.value)}
        placeholder="Optional: what could be better?"
        className="w-full bg-muted/30 border border-border rounded-lg p-2 text-sm resize-none h-16" />
      <Button onClick={submit} disabled={rating === 0} size="sm" className="gap-1.5">
        <Send className="w-3 h-3" /> Submit Feedback
      </Button>
    </div>
  );
}
```

### 13E. Inject lessons into P5 prompts

In `pipeline/phases/p5_build.py`, when calling `_generate_skill_md()`, fetch domain lessons:

This requires passing lessons through the pipeline. Add to `BuildConfig`:
```python
domain_lessons: str = ""  # Injected by build-runner from feedback DB
```

In `build-runner.ts`, when spawning pipeline, query feedback and pass as env:
```typescript
const { getDomainLessons } = require("@/lib/feedback");
const lessons = getDomainLessons(config.domain || "");
// Pass as env var or write to temp file
```

In P5 prompts, append to user prompt:
```python
# If lessons available, append to P5_SKILL_USER:
if config.domain_lessons:
    user_prompt += f"\n\n{config.domain_lessons}\n\nUse these lessons to avoid known issues."
```

---


## ═══════════════════════════════════════════════════════════
## MASTER CHECKLIST & TIMELINE (UPDATED — 5 VÒNG REVIEW)
## ═══════════════════════════════════════════════════════════

```
SPRINT 1 — Quick Wins (Tuần 1, ~4 ngày):
  □ TASK 1: Pushy P5 prompts                    [0.5d] [Idea #2]
  □ TASK 2: Progressive Disclosure enforcer      [0.5d] [Idea #3]
  □ TASK 3: WHY-driven ALL prompts (P1-P5)       [1.5d] [Idea #5]
  □ TASK 7: Multi-Model Strategy (config-based)  [0.5d] [Idea #10] ← REWRITTEN
  → pytest + manual build test

SPRINT 2 — Core Features (Tuần 2, ~4-5 ngày):
  □ TASK 4: P6 Description Optimizer             [2-3d] [Idea #1] ← 9 PATCHES APPLIED
    ├── 4A: Prompts file
    ├── 4B: p6_optimize.py (PyYAML + no RUNS + decoys)
    ├── 4C: types.py PhaseId enum
    ├── 4D: runner.py (PHASES + P55 inline + resume)
    ├── 4E: types/build.ts (PhaseId + PHASES)
    ├── 4F: phase-stepper.tsx (PHASE_COLORS)
    ├── 4G: use-build-stream.ts (INITIAL_PHASES) ← NEW
    └── 4H: logger.py (assert guard) ← NEW
  □ TASK 5: P5.5 Smoke Test (inline sub-step)   [1-2d] [Idea #4] ← OPTION A
  □ TASK 6: Unit tests for all new code          [0.5d]
  → pytest + E2E build test + npm run build

SPRINT 3 — Quality & UI (Tuần 3, ~5-6 ngày):
  □ TASK 8: Eval Query Generator UI              [2-3d] [Idea #6]
  □ TASK 9: Build History & A/B Compare          [2-3d] [Idea #7]
  □ TASK 10: Script Auto-Bundler                 [1-2d] [Idea #8]
  □ TASK 11: Quality Report 2.0                  [1-2d] [Idea #9]
  □ TASK 14: PHASE_ORDER refactor (bonus)        [10m]  ← NEW
  → Full UI test

SPRINT 4 — Advanced (Tuần 4+, ~4-6 ngày):
  □ TASK 12: Enhanced Template Library            [2-3d] [Idea #11]
  □ TASK 13: Self-Improving Pipeline              [2-3d] [Idea #12]
  → Integration test + feedback loop test

TOTAL: ~17-22 ngày (~4 tuần)
```

### 4 Sync Points Checklist (P6 trên frontend — chạy sau Task 4E-4G)
```
□ types/build.ts      → PhaseId type có "p6"
□ types/build.ts      → PHASES array có P6 entry
□ use-build-stream.ts → INITIAL_PHASES có P6 entry
□ phase-stepper.tsx   → PHASE_COLORS có p6 color
```

### Validation sau mỗi Sprint:
```bash
# Unit tests
cd pipeline && python -m pytest tests/ -x -v

# Import check all new modules
python -c "
from pipeline.phases.p6_optimize import run_p6
from pipeline.phases.p55_smoke_test import run_p55
from pipeline.core.types import PHASE_MODEL_MAP, BuildConfig
# Verify backward compat:
c = BuildConfig(name='test', domain='test')
assert c.phase_model_hints == {}, 'Default should be empty dict'
print('All imports OK')
"

# Verify PyYAML on production data
python -c "
from pipeline.phases.p6_optimize import _extract_description
with open('output/fb-ads-meta/SKILL.md') as f:
    content = f.read()
desc = _extract_description(content)
assert len(desc) > 50 and '>' not in desc[:5], f'PyYAML failed: {desc[:30]}'
print(f'✅ PyYAML: {desc[:60]}... ({len(desc)} chars)')
"

# Verify guard
python -c "
from pipeline.core.logger import PipelineLogger
logger = PipelineLogger('test')
# phase_start('p55') should warn and return, NOT emit phase event
import io, sys
old_stdout = sys.stdout
sys.stdout = io.StringIO()
logger.phase_start('p55', 'Test')
output = sys.stdout.getvalue()
sys.stdout = old_stdout
assert '\"event\": \"phase\"' not in output, 'Guard failed — phase event emitted for p55!'
print('✅ Guard works: phase_start(p55) silently skipped')
"

# Frontend
npm run build  # TypeScript compile check
npm run dev    # Manual test — verify P6 shows on stepper
```

### Metrics thành công:
- Triggering accuracy: >80% (đo bằng P6 test score)
- Smoke test pass rate: >60%
- Cost efficiency: Draft tier giảm 40%+ vs current
- Build time: <25 phút cho Standard tier (including P6)
- User satisfaction: 4.0+/5 (tracked by feedback system)

### Doc cần update (không ảnh hưởng code):
- `docs/PROJECT-CONTEXT.md` line 697: Sửa "logger dùng ensure_ascii=True" thành
  "logger dùng ensure_ascii=False với fallback True nếu UnicodeEncodeError" (code đúng, doc sai)
