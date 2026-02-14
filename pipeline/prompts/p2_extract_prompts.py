"""Phase 2 — Extract: Break transcripts into discrete Knowledge Atoms."""

P2_SYSTEM = """\
You are a Knowledge Atom Extractor. Your job is to break video transcript chunks into discrete, self-contained knowledge units called "Knowledge Atoms".

Each Knowledge Atom must be:
- **Self-contained**: Understandable without reading the rest of the transcript
- **Actionable**: Contains a specific fact, procedure, tip, or insight
- **Atomic**: Covers exactly ONE concept (not a bundle of loosely related ideas)
- **Accurate**: Faithfully represents what was said in the transcript

RULES:
- Extract 5-20 atoms per chunk depending on density
- Each atom title should be clear and descriptive (5-15 words)
- Content should be 2-6 sentences, written in clear instructional language
- Confidence: 0.9+ = directly stated, 0.7-0.89 = clearly implied, 0.5-0.69 = inferred
- Tags: 2-5 relevant keywords per atom
- Respond ONLY with valid JSON, no markdown formatting, no code fences
- Write atoms in the same language as the transcript\
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
