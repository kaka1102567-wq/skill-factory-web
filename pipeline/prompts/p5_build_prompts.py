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
