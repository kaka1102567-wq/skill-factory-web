"""Phase 5 — Build: Generate final SKILL.md and knowledge files."""

P5_SKILL_SYSTEM = """\
You are an AI Skill Architect. Your task is to create a professional SKILL.md file that serves as the master index for an AI knowledge skill package.

The SKILL.md file must:
1. Clearly define the skill's purpose and scope
2. List all knowledge pillars (categories) with descriptions
3. Reference the knowledge files that contain detailed atoms
4. Include usage instructions for AI assistants
5. Be well-structured with proper Markdown formatting

RULES:
- Write in the specified language
- Use clear, professional language suitable for AI consumption
- Structure with proper headings, lists, and descriptions
- Include a metadata header with skill name, domain, version, atom count
- Respond ONLY with valid JSON containing the "content" field, no markdown fences around the JSON\
"""

P5_SKILL_USER = """\
Create a SKILL.md file for this AI knowledge skill.

**Skill name:** {name}
**Domain:** {domain}
**Language:** {language}
**Knowledge pillars:** {pillars}
**Total verified atoms:** {atom_count}
**Quality tier:** {quality_tier}

Return a JSON object with this EXACT structure:
{{
  "content": "The full SKILL.md content as a string with proper Markdown formatting",
  "metadata": {{
    "name": "{name}",
    "domain": "{domain}",
    "language": "{language}",
    "version": "1.0.0",
    "atom_count": {atom_count},
    "pillar_count": 0,
    "quality_tier": "{quality_tier}"
  }}
}}\
"""

P5_KNOWLEDGE_SYSTEM = """\
You are a Knowledge File Writer. Your task is to organize a set of verified Knowledge Atoms into a well-structured knowledge file for a specific pillar (category).

The knowledge file must:
1. Group atoms logically within the pillar
2. Present each atom clearly with its title, content, and metadata
3. Use consistent Markdown formatting
4. Be optimized for AI retrieval — clear headings, structured content

RULES:
- Each atom should be a separate section with ## heading
- Include atom tags and confidence score as metadata
- Write in the specified language
- Order atoms from most fundamental to most advanced
- Respond ONLY with valid JSON containing the "content" field, no markdown fences around the JSON\
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
