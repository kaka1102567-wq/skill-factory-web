"""Phase 3 — Dedup: Deduplicate and merge overlapping Knowledge Atoms."""

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

P3_USER_TEMPLATE = """\
Analyze these {atom_count} Knowledge Atoms for duplicates, overlaps, and conflicts.

**Language:** {language}
**Domain:** {domain}

--- ATOMS START ---
{atoms_json}
--- ATOMS END ---

Return a JSON object with this EXACT structure:
{{
  "unique_atoms": [
    {{
      "id": "original or merged atom ID",
      "title": "Best title",
      "content": "Merged/best content",
      "category": "category_id",
      "tags": ["tag1", "tag2"],
      "confidence": 0.9,
      "status": "deduplicated",
      "merged_from": ["id1", "id2"]
    }}
  ],
  "duplicates_merged": 0,
  "overlaps_merged": 0,
  "conflicts": [
    {{
      "atom_a_id": "id of first conflicting atom",
      "atom_b_id": "id of second conflicting atom",
      "conflict_type": "contradictory_data",
      "description": "What specifically contradicts between these atoms"
    }}
  ],
  "stats": {{
    "input_count": {atom_count},
    "output_count": 0,
    "duplicates_found": 0,
    "conflicts_found": 0
  }}
}}\
"""
