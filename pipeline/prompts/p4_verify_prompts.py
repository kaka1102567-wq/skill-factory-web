"""Phase 4 — Verify: Cross-reference atoms against baseline knowledge."""

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
