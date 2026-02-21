"""Prompt templates for Auto-Baseline Discovery from input content."""

# ── Domain inference from input content (used by auto_discovery) ──

INFER_DOMAIN_SYSTEM = """You are a content analyst. Given text samples from uploaded documents,
determine the actual domain/topic. Return ONLY valid JSON."""

INFER_DOMAIN_USER_TEMPLATE = """Analyze these content samples and determine the real domain/topic.

Content samples:
{content_samples}

Return JSON:
{{
  "inferred_domain": "short-kebab-case-domain",
  "display_name": "Human readable name",
  "key_topics": ["topic1", "topic2", "topic3", "topic4", "topic5"],
  "search_terms": [
    "specific search query 1",
    "specific search query 2",
    "specific search query 3",
    "specific search query 4",
    "specific search query 5",
    "specific search query 6"
  ]
}}

Rules:
- search_terms should be Google-friendly queries (3-6 words each)
- Include 6-8 search_terms covering different aspects
- key_topics should be 5-8 specific topics from the content
- inferred_domain should be a short identifier like "ai-agent-retail" or "machine-learning-nlp"
"""


# ── Content Analysis prompts (used by discover-from-content command) ──

SYSTEM_ANALYZE_CONTENT = """You are a Content Analysis Expert. Given sample text from educational/training materials, identify:
1. The main domain/topic
2. Key subtopics covered
3. Search queries to find official reference documentation

Rules:
- Identify the SPECIFIC domain (e.g. "Facebook Ads Manager" not just "advertising")
- Generate 5-8 search queries targeting OFFICIAL documentation, guides, and best practices
- Detect the content language and match search queries to it
- Topics should be specific and actionable

RESPOND IN VALID JSON ONLY. No markdown, no explanation."""

USER_ANALYZE_CONTENT = """Analyze these content samples from training materials:

---SAMPLES START---
{samples_text}
---SAMPLES END---

Return JSON:
{{
  "domain": "specific domain/topic name",
  "language": "detected content language (e.g. vi, en)",
  "topics": ["15-25 specific topics covered in the content"],
  "search_queries": ["5-8 search queries to find official reference docs for this domain"],
  "official_sites": ["known official documentation URLs if identifiable"],
  "content_type": "course|tutorial|documentation|reference|mixed"
}}"""

SYSTEM_EVALUATE_URLS = """You are a Documentation Quality Evaluator. Given a list of URLs with titles and snippets, score their relevance for building a knowledge base about a specific domain.

Rules:
- Score 0-100 based on relevance, authority, and content quality
- Prioritize official documentation over blog posts
- Prioritize comprehensive guides over short articles
- Exclude login pages, ads, unrelated content

RESPOND IN VALID JSON ONLY."""

USER_EVALUATE_URLS = """Domain: {domain}
Topics: {topics}

Evaluate these URLs:
{urls_text}

Return JSON array:
[
  {{"url": "...", "score": 85, "reason": "brief reason"}},
  ...
]
Only include URLs with score >= 40. Sort by score descending."""
