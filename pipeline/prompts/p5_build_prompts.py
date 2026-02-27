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

2. SKILL.md BODY must include these sections IN THIS ORDER:
   a. Purpose statement (1-2 sentences explaining what this skill contains)
   b. "Agent Instructions" section with subsections:
      - "Scope": IN SCOPE (from domain + categories) and OUT OF SCOPE (infer from domain boundaries)
      - "Decision Tree": Intent-based routing tree using actual knowledge pillars. Format:
        User hỏi về [domain]?
        ├─ Hỏi KHÁI NIỆM → [pillar].md §Core
        ├─ Hỏi THỰC HÀNH → [pillar].md + [pillar2].md
        ├─ Hỏi SO SÁNH → đọc 2 sections → bảng so sánh
        ├─ Hỏi CHIẾN LƯỢC → strategy/advanced sections
        └─ NGOÀI SCOPE → từ chối + gợi ý
      - "Confidence Map": Include the provided confidence_map text VERBATIM (do not modify it)
   c. "Knowledge Pillars" — list all pillars with atom counts and file references
   d. "Composition Patterns" — Generate 3-4 answer composition patterns for this domain:
      e.g., Definition + Example + Comparison, Problem → Solution → Tool, Timeline → Current → Future
   e. "Failure Modes" — Generate 4-5 domain-specific failure modes. Each must have:
      ### Lỗi N: [Mô tả]
      WRONG: "..." (example bad response)
      RIGHT: "..." (example good response)
      WHY AGENTS FAIL: [root cause]
   f. Expert Tips (if available from unverified-in-docs atoms)
   g. Advanced Strategies (if available from high-confidence atoms)
   h. References (if baseline references exist)
   i. "Q&A Examples" (if available)
   j. "Limitations" — what this skill does NOT cover, scope boundaries
   - Keep under 500 lines total — if content is longer, reference knowledge/*.md files

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

CONFIDENCE MAP (include verbatim in Agent Instructions > Confidence Map):
{confidence_map}

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

AGENT-READY SECTIONS — Generate these based on the knowledge pillars:
1. Agent Instructions with Scope (IN/OUT), Decision Tree (routing based on user intent to correct pillar), and the Confidence Map provided above (verbatim)
2. Composition Patterns (3-4 patterns suited for {domain})
3. Failure Modes (4-5 domain-specific mistakes agents commonly make, each with WRONG/RIGHT examples and WHY AGENTS FAIL root cause)

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

REQUIRED FILE STRUCTURE:
Every knowledge file MUST begin with these 3 elements in order:

1. HEADING: # {Pillar Title}
2. SUMMARY LINE: > 1-sentence description of what this file contains and when to read it.
3. TABLE OF CONTENTS: ## Table of Contents with numbered links to each section below.

Then a --- separator, followed by the detailed atom sections.

Example opening:
```
# Campaign Management

> Contains 8 concepts about campaign setup, budgeting, and optimization.
> Read this file when the user asks about creating, managing, or improving ad campaigns.

## Table of Contents
1. Campaign Structure Best Practices
2. Budget Allocation Strategy
3. A/B Testing Framework
...

---
```

ORGANIZATION INTO 3 TIERS:
Organize atoms into 3 tiers based on importance and verification status:

## 🔑 Core (read first — answers 80% of questions)
[Most important atoms, grouped by sub-topic. Prioritize atoms with high confidence + verified status]

## 📚 Detail (read when deeper dive needed)
[Detailed atoms, technical depth, specific examples]

## 💡 Insights (read when expert perspective needed)
[Expert analysis, predictions, comparisons — atoms with source="baseline" or gap_filled=true]

Use atom confidence, status, and source fields to determine tier placement.
Do NOT add per-atom metadata tags — keep knowledge files clean and readable.

ORGANIZATION PRINCIPLES:
- Within each tier, order atoms from most fundamental to most advanced
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

P5_QA_EXAMPLES_SYSTEM = """\
You are generating realistic Q&A examples for an AI knowledge skill.
These examples will be included in the skill package so that AI assistants
can see HOW to answer questions using this skill's knowledge.

RULES:
- Generate exactly {count} Q&A pairs
- Each question must sound like a real user asking naturally
- Each answer must be derived ONLY from the provided knowledge atoms
- Answers should be concise (2-4 sentences), demonstrating how the skill's knowledge is applied
- Cover different categories/pillars to show the skill's breadth
- Include 1 simple, 1 applied, and 1 comparison question
- Write in the specified language
- Respond ONLY with valid JSON\
"""

P5_QA_EXAMPLES_USER = """\
Generate {count} Q&A examples for this skill:

**Skill name:** {name}
**Domain:** {domain}
**Language:** {language}

**Top knowledge atoms (use ONLY these as source):**
{atoms_json}

Return JSON:
{{
  "examples": [
    {{
      "question": "A natural user question",
      "answer": "Concise answer using knowledge from the atoms above",
      "source_atoms": ["atom_id_1"],
      "type": "simple|applied|comparison"
    }}
  ]
}}\
"""
