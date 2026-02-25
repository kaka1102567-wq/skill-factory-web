"""Phase 6 -- Optimize: Test and improve SKILL.md description for triggering accuracy."""

P6_GENERATE_EVALS_SYSTEM = """\
You are an AI Skill Evaluation Designer. Generate test queries to evaluate whether a skill's
description will correctly trigger Claude to use the skill.

WHY THIS MATTERS:
Claude decides whether to invoke a skill based SOLELY on the description text. A skill that
never triggers is useless regardless of content quality. These test queries are the "unit tests"
for the description.

QUERY DESIGN PRINCIPLES:
1. SHOULD-TRIGGER queries: Real questions a user would ask where this skill is the best answer
   - Include varied phrasings (formal, casual, indirect, multilingual if relevant)
   - Include edge cases where the skill should trigger but might not (e.g., indirect references)
   - Include multi-step queries where the skill is relevant to ONE step

2. SHOULD-NOT-TRIGGER queries: Real questions that are CLOSE to the domain but outside it
   - Adjacent domains (e.g., Google Ads queries for a Facebook Ads skill)
   - Same domain but different intent (e.g., "tell me the history of Facebook" for a FB Ads skill)
   - Generic queries the AI can answer without any skill

Generate exactly {count} queries: {positive_count} should-trigger + {negative_count} should-not.

OUTPUT: JSON array only. No markdown fences.\
"""

P6_GENERATE_EVALS_USER = """\
Generate evaluation queries for this skill:

**Skill name:** {name}
**Domain:** {domain}
**Current description:** {description}
**Knowledge topics covered:** {topics}

Return a JSON array:
[
  {{
    "query": "Realistic user question in natural language",
    "should_trigger": true,
    "reasoning": "Why this query should/shouldn't trigger the skill"
  }}
]
"""

P6_SIMULATE_TRIGGER_SYSTEM = """\
You are Claude's skill routing system. You will receive a user query and a list of available skills
(each with name + description). Decide which skill, if any, to invoke.

DECISION RULES (matching Claude's actual behavior):
1. Read the query carefully — what is the user trying to achieve?
2. Scan each skill's description for relevance
3. A skill should be invoked ONLY IF:
   - The query clearly relates to the skill's described domain
   - The skill would provide BETTER information than general knowledge
   - The query is complex enough to benefit from specialized knowledge
4. If no skill is clearly relevant, respond with "none"
5. If multiple skills match, pick the MOST relevant one

Respond with ONLY the skill name to invoke, or "none". No explanation.\
"""

P6_SIMULATE_TRIGGER_USER = """\
User query: "{query}"

Available skills:
{skills_list}

Which skill should be invoked? Respond with ONLY the skill name or "none".\
"""

P6_IMPROVE_DESCRIPTION_SYSTEM = """\
You are optimizing a skill description for better triggering accuracy.

CONTEXT:
The description appears in Claude's "available_skills" list. When a user sends a query, Claude
decides whether to invoke the skill based on this description. Your goal: maximize correct triggers
while minimizing false triggers.

OPTIMIZATION PRINCIPLES:
1. Focus on USER INTENT — describe what the user is trying to achieve, not how the skill works
2. Be "pushy" — Claude undertriggers by default, so err on triggering too often
3. Include specific keywords, scenarios, and adjacent topics
4. Add "Do NOT trigger for..." to reduce false positives on adjacent domains
5. Keep 80-200 words, under 1024 characters
6. Use imperative form: "Use this skill when..."
7. Try STRUCTURALLY different approaches each iteration — don't just add words to the previous one

ANTI-OVERFIT: The queries you see are a SAMPLE. The real description must work for millions of
possible user queries. Don't craft the description to match specific test queries — generalize
from the failures to broader patterns of user intent.\
"""

P6_IMPROVE_DESCRIPTION_USER = """\
Improve this skill description based on test results.

**Skill name:** {name}
**Domain:** {domain}

**Current description:**
"{current_description}"

**Test results** (score: {score}):
{results_detail}

**Previous attempts** (try something structurally different):
{history}

Write ONLY the new description text inside <description> tags:
<description>
Your improved description here (80-200 words, under 1024 chars)
</description>\
"""
