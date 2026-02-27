"""Phase 2 — Extract: Break transcripts into discrete Knowledge Atoms."""

PROMPT_VERSION = "p2_extract_v1"

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

P2_USER_TEMPLATE = """\
Extract Knowledge Atoms from this transcript chunk.

**Chunk:** {chunk_index} of {total_chunks}
**Language:** {language}
**Domain:** {domain}
**Available categories:** {categories}
**Source file:** {filename}

--- CHUNK START ---
{chunk}
--- CHUNK END ---

Return a JSON object with this EXACT structure:
{{
  "chunk_index": {chunk_index},
  "atoms": [
    {{
      "title": "Clear descriptive title of the knowledge atom",
      "content": "2-6 sentences of self-contained knowledge. Written in clear instructional language.",
      "category": "category_id from the provided list",
      "tags": ["keyword1", "keyword2", "keyword3"],
      "confidence": 0.85,
      "source_timestamp": "approximate location in transcript if identifiable, else null"
    }}
  ],
  "atoms_count": 0,
  "chunk_quality": "high"
}}\
"""

# ── Gap-fill: extract atoms from baseline reference docs ──

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

P2_GAP_USER_TEMPLATE = """\
Extract 1-3 Knowledge Atoms about the topic "{topic}" from this reference documentation.

**Language:** {language}
**Domain:** {domain}
**Available categories:** {categories}
**Reference file:** {ref_file}

--- REFERENCE EXCERPT START ---
{content}
--- REFERENCE EXCERPT END ---

Return a JSON object with this EXACT structure:
{{
  "topic": "{topic}",
  "atoms": [
    {{
      "title": "Clear descriptive title of the knowledge atom",
      "content": "2-6 sentences of self-contained knowledge from the docs.",
      "category": "category_id from the provided list",
      "tags": ["keyword1", "keyword2", "keyword3"],
      "confidence": 0.92
    }}
  ],
  "atoms_count": 0
}}\
"""

# ── Code pattern extraction: extract atoms from source code analysis ──

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

P2_CODE_USER_TEMPLATE = """\
Extract knowledge atoms from these source code files.

**Repository structure:**
{repo_structure}

**Source files to analyze:**
{files}

Extract up to {max_atoms} knowledge atoms in {language}.

Return a JSON object with this EXACT structure:
{{
  "atoms": [
    {{
      "title": "Pattern name or concept",
      "content": "Detailed explanation of the pattern, why it is used, when to apply it.",
      "tags": ["tag1", "tag2"],
      "code_snippet": "key code example (10-30 lines max)",
      "file_reference": "path/to/file.py",
      "pattern_type": "architecture|function|configuration|error_handling|integration|best_practice",
      "confidence": 0.85
    }}
  ],
  "atoms_count": 0
}}\
"""
