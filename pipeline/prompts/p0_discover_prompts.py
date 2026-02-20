"""Prompt templates for Auto-Baseline Discovery from input content."""

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
