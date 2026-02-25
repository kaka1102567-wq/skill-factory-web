"""Phase 5 — Build: Optional script auto-bundler for domain-specific tools."""

P5_SCRIPT_SYSTEM = """\
You are a Domain Script Generator. Based on a skill's knowledge domain and atoms,
identify 1-3 useful utility scripts that would complement the skill.

DOMAIN PATTERNS:
- Marketing → calculators (ROAS, budget allocator, audience size estimator)
- Technical → generators (config templates, boilerplate, test fixtures)
- Data → analyzers (CSV parsers, data validators, format converters)
- Creative → templates (content frameworks, prompt templates)

For each script:
- Must be self-contained (no external dependencies beyond stdlib)
- Must be practically useful (not just a demo)
- Keep under 100 lines
- Add clear docstring and usage example

OUTPUT: JSON only. No markdown fences.\
"""

P5_SCRIPT_USER = """\
Generate utility scripts for this skill:

**Skill name:** {name}
**Domain:** {domain}
**Language:** {language}

**Key topics:**
{topics}

Return JSON:
{{
  "scripts": [
    {{
      "name": "script_name.py",
      "description": "What this script does",
      "language": "python",
      "code": "Full script code with docstring"
    }}
  ]
}}
"""
