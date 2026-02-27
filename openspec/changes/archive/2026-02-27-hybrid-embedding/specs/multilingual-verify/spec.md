## ADDED Requirements

### Requirement: Embedding-based verification replaces keyword matching
P4 verify SHALL use embedding similarity to match atoms against baseline references instead of keyword matching. Three tiers: verified (≥0.70), partially_verified (0.50-0.70), expert_insight (<0.50).

#### Scenario: High similarity verified
- **WHEN** atom has embedding similarity ≥ 0.70 against a baseline reference
- **THEN** status is "verified" with score and matched reference path in verification_note

#### Scenario: Medium similarity partial
- **WHEN** atom has embedding similarity between 0.50 and 0.70
- **THEN** status is "partially_verified" with score and matched reference path

#### Scenario: Low similarity expert insight
- **WHEN** atom has embedding similarity < 0.50 against all baseline references
- **THEN** status is "expert_insight" with best match score noted

#### Scenario: No baseline references
- **WHEN** no baseline references exist for verification
- **THEN** status is "expert_insight" with score 0.0

### Requirement: Score included in verification note
P4 SHALL write the embedding score into `verification_note` field in format: `"Verified (score 0.85) against ref.md"`. This enables P5 Confidence Map to parse and categorize.

#### Scenario: Score format in note
- **WHEN** P4 verifies an atom with embedding
- **THEN** verification_note contains `score X.XX` parseable by regex `score\s+([\d.]+)`

### Requirement: Keyword matching fallback
When embedding API is unavailable, P4 SHALL fall back to existing keyword matching logic. No functionality regression.

#### Scenario: No embedding fallback
- **WHEN** embedding client is unavailable or has no API key
- **THEN** P4 uses existing keyword matching logic (identical to pre-Sprint 3)

### Requirement: Cross-language matching
Embedding similarity SHALL correctly match semantically equivalent content across languages (e.g., Vietnamese ↔ English).

#### Scenario: Vietnamese vs English match
- **WHEN** atom "Cach toi uu chi phi quang cao" is compared to baseline "How to reduce Facebook Ads spend"
- **THEN** embedding similarity is significantly higher than keyword matching (which returns 0)
