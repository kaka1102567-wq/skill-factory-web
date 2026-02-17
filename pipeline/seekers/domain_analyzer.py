"""Domain Analyzer — uses Claude Haiku to analyze a domain and suggest doc sources."""

import json
from dataclasses import dataclass, field


@dataclass
class DomainAnalysis:
    domain: str
    official_sites: list[str] = field(default_factory=list)
    doc_patterns: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    expected_topics: list[str] = field(default_factory=list)
    difficulty: str = "medium"  # easy|medium|hard
    notes: str = ""


_SYSTEM_PROMPT = """You are a Documentation Research Expert. Given a domain/topic name, identify the BEST official documentation sources for building an AI knowledge base.

Rules:
- Prioritize OFFICIAL documentation over third-party
- Include beginner guides AND API/technical docs
- Generate 5-8 diverse search queries
- Flag JS-rendered sites in notes

RESPOND IN VALID JSON ONLY. No markdown, no explanation."""

_USER_TEMPLATE = """Domain: {domain}
Target language: {language}

Return JSON:
{{
  "official_sites": ["base URLs of official documentation sites"],
  "doc_patterns": ["URL path patterns like /docs/, /help/, /guide/"],
  "search_queries": ["5-8 search queries to find best docs for this domain"],
  "expected_topics": ["15-25 key topics this domain should cover"],
  "difficulty": "easy|medium|hard",
  "notes": "special notes about crawling this domain"
}}"""


def analyze_domain(domain: str, language: str, claude_client, logger) -> DomainAnalysis:
    """Call Claude Haiku once to analyze a domain.

    Returns DomainAnalysis with official_sites, search_queries, expected_topics.
    Uses use_light_model=True (Haiku, cheap).
    On parse failure, returns a DomainAnalysis with basic default queries.
    """
    user_msg = _USER_TEMPLATE.format(domain=domain, language=language)

    logger.info(f"Analyzing domain: {domain}", phase="discovery")

    try:
        response = claude_client.call(
            system=_SYSTEM_PROMPT,
            user=user_msg,
            max_tokens=2000,
            use_light_model=True,
        )
        data = json.loads(response)
        result = DomainAnalysis(
            domain=domain,
            official_sites=data.get("official_sites", []),
            doc_patterns=data.get("doc_patterns", ["/docs/", "/help/", "/guide/"]),
            search_queries=data.get("search_queries", [f"{domain} official documentation"]),
            expected_topics=data.get("expected_topics", []),
            difficulty=data.get("difficulty", "medium"),
            notes=data.get("notes", ""),
        )
        logger.info(
            f"Domain analysis: {len(result.official_sites)} sites, "
            f"{len(result.search_queries)} queries, difficulty={result.difficulty}",
            phase="discovery",
        )
        return result
    except (json.JSONDecodeError, Exception) as e:
        logger.warn(f"Domain analysis parse error: {e}, using defaults", phase="discovery")
        return DomainAnalysis(
            domain=domain,
            search_queries=[
                f"{domain} official documentation",
                f"{domain} tutorial guide",
                f"{domain} API reference",
                f"{domain} best practices",
                f"{domain} getting started",
            ],
            expected_topics=[],
            difficulty="medium",
        )
