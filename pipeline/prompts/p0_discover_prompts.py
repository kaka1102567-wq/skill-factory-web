"""Prompt templates for Auto-Baseline Discovery from input content."""

# ── Domain inference from input content (used by auto_discovery) ──

INFER_DOMAIN_SYSTEM = """Ban la chuyen gia phan tich noi dung. Nhiem vu: xac dinh chu de/linh vuc chinh xac tu ten file va noi dung mau.
Tra ve CHI JSON hop le, khong co markdown hay text khac."""

INFER_DOMAIN_USER_TEMPLATE = """Phan tich noi dung sau va xac dinh chu de chinh xac.

## Ten files:
{file_names}

## Noi dung mau:
{content_samples}

## Yeu cau:
Tra ve JSON:
{{
  "inferred_domain": "slug-tieng-anh-khong-dau",
  "display_name": "Ten chu de day du",
  "key_topics": ["topic1", "topic2", "topic3", "topic4", "topic5"],
  "search_terms": [
    "cau tim kiem Google 1",
    "cau tim kiem Google 2",
    "cau tim kiem Google 3",
    "cau tim kiem Google 4",
    "English search query 5",
    "English search query 6",
    "cau tim kiem Google 7",
    "English search query 8"
  ]
}}

Luu y:
- Ten file rat co gia tri — "CHUONG 5 AI Agent Cham soc suc khoe.pdf" cho thay chu de la AI Agent trong y te
- search_terms phai la cau tim kiem THUC TE tren Google, mix tieng Viet + Anh
- Vi du: neu noi dung ve AI Agent -> queries: "ung dung AI agent doanh nghiep", "AI agent customer service guide", "LLM agent tutorial"
- KHONG search tu khoa generic nhu "documentation" hay "guide" hay "custom"
- Uu tien trang chinh thong: docs, tutorials, research papers
- key_topics la 5-8 chu de cu the tu noi dung
- inferred_domain la slug ngan nhu "ai-agent-ung-dung" hoac "machine-learning-nlp"
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
