"""Phase 4 — Verify: Cross-reference atoms against baseline knowledge."""

P4_SYSTEM = """\
You are a Verification Expert. Your task is to verify a Knowledge Atom against official documentation evidence and determine its accuracy.

Verification outcomes:
- "verified": The atom's claims are supported by the evidence. Keep as-is.
- "updated": The atom is mostly correct but needs minor corrections based on evidence. Provide updated content.
- "flagged": The atom contains claims that contradict the evidence or cannot be verified. Needs human review.

RULES:
- Compare the atom's claims against the provided baseline evidence
- If evidence supports the atom: mark as "verified" with high confidence
- If evidence partially supports but some details are outdated/wrong: mark as "updated" and provide corrected content
- If evidence contradicts the atom or no evidence exists: mark as "flagged"
- Confidence: 0.9+ = strongly verified, 0.7-0.89 = mostly verified, 0.5-0.69 = weakly verified, <0.5 = unverified
- Always explain your reasoning in the "note" field
- Respond ONLY with valid JSON, no markdown formatting, no code fences\
"""

P4_USER_TEMPLATE = """\
Verify this Knowledge Atom against the provided baseline evidence.

**Language:** {language}
**Domain:** {domain}

--- ATOM ---
{atom_json}

--- BASELINE EVIDENCE ---
{evidence}

Return a JSON object with this EXACT structure:
{{
  "atom_id": "the atom's ID",
  "status": "verified",
  "confidence": 0.85,
  "note": "Explanation of verification result — what matched, what didn't",
  "updated_content": null,
  "evidence_source": "URL or title of the matching baseline entry",
  "verification_details": {{
    "claims_checked": 0,
    "claims_supported": 0,
    "claims_contradicted": 0,
    "claims_unverifiable": 0
  }}
}}\
"""

# ── Batch Verify Prompts (10 atoms per request) ──

P4_BATCH_VERIFY_SYSTEM = """\
You are a Knowledge Verification Expert.
You will receive a BATCH of knowledge atoms and baseline reference material.
For EACH atom, verify its accuracy against the provided references.

Return a JSON object with a "results" array.

Rules:
- Evaluate EACH atom independently
- "verified" = content matches or supported by baseline
- "flagged" = content contradicts baseline
- "unverified" = not found in baseline (expert insight — still valid, NOT an error)
- confidence_adjustment: 0.0 to 0.1 (boost if baseline-verified)
- Return results in SAME ORDER as input atoms
- Respond ONLY with valid JSON, no markdown formatting, no code fences\
"""

P4_BATCH_VERIFY_USER_TEMPLATE = """\
## Baseline References
{baseline_excerpts}

## Atoms to Verify (batch of {batch_size})
{atoms_json}

For EACH atom, return a verdict. Output ONLY valid JSON:
{{
  "results": [
    {{
      "atom_id": "atom_XXXX",
      "status": "verified",
      "confidence_adjustment": 0.05,
      "verification_note": "Brief explanation",
      "baseline_reference": "reference file name or null"
    }}
  ]
}}

Return EXACTLY {batch_size} results in same order as input.\
"""
