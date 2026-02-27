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
   b. "When to Use This Skill" — list 3-6 specific trigger scenarios
   c. "Workflow" — numbered steps the AI should follow when using this skill
   d. "Routing Logic" — which knowledge/*.md or references/ file to read for which topic
   e. "Knowledge Pillars" — list all pillars with atom counts and file references
   f. Expert Tips (if available from unverified-in-docs atoms)
   g. Advanced Strategies (if available from high-confidence atoms)
   h. "Limitations" — what this skill does NOT cover, scope boundaries
   i. References (if baseline references exist)
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
