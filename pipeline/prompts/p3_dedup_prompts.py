"""Phase 3 — Dedup: Deduplicate and merge overlapping Knowledge Atoms."""

P3_SYSTEM = """\
You are a Deduplication Expert for knowledge management. Your task is to analyze a batch of Knowledge Atoms and:

1. Identify duplicate or near-duplicate atoms (same concept, different wording)
2. Identify overlapping atoms (partial overlap in content)
3. Merge duplicates into a single, improved atom keeping the best information from each
4. Flag genuine conflicts where atoms contradict each other

RULES for deduplication:
- Two atoms are "duplicate" if they describe the SAME specific fact/procedure with >80% content overlap
- Two atoms "overlap" if they share some content but each has unique information — merge them
- Two atoms "conflict" if they state contradictory information about the same topic
- When merging, keep the higher confidence score and combine unique details
- Preserve the atom ID of the higher-quality original
- Respond ONLY with valid JSON, no markdown formatting, no code fences\
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
