"""Auto-Discovery Orchestrator — entry point for the full auto-discovery pipeline."""

import json
import os
import re
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path

from .domain_analyzer import analyze_domain, DomainAnalysis
from .url_discoverer import discover_urls
from .url_evaluator import evaluate_urls
from .scraper import smart_crawl

DISCOVERY_TIMEOUT_SECONDS = 300  # 5 minutes

# Domains that are too generic to search directly
GENERIC_DOMAINS = frozenset({
    "custom", "unknown", "general", "other", "misc", "test", "default",
})
MAX_INFER_FILES = 3
MAX_INFER_CHARS = 2000


class DiscoveryTimeoutError(Exception):
    """Raised when discovery exceeds the time limit."""
    pass


@dataclass
class DiscoveryResult:
    success: bool
    output_dir: str = ""
    refs_count: int = 0
    topics_count: int = 0
    total_cost_usd: float = 0.0
    discovery_metadata: dict = field(default_factory=dict)


def _is_generic_domain(domain: str) -> bool:
    """Check if domain name is too generic to produce useful search queries."""
    return domain.lower().strip() in GENERIC_DOMAINS or len(domain.strip()) <= 3


def _infer_domain_from_content(input_dir: str, claude_client, logger) -> dict | None:
    """Read input files and use Claude to infer the real domain/topic.

    Returns dict with inferred_domain, display_name, key_topics, search_terms
    or None if inference fails.
    """
    from ..prompts.p0_discover_prompts import (
        INFER_DOMAIN_SYSTEM, INFER_DOMAIN_USER_TEMPLATE,
    )

    input_path = Path(input_dir)
    if not input_path.is_dir():
        return None

    text_files = sorted(
        f for f in input_path.iterdir()
        if f.suffix in (".md", ".txt") and f.is_file()
    )
    if not text_files:
        return None

    # Read up to MAX_INFER_FILES, each truncated to MAX_INFER_CHARS
    content_samples = ""
    for f in text_files[:MAX_INFER_FILES]:
        try:
            text = f.read_text(encoding="utf-8")
            # Strip YAML frontmatter
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    text = text[end + 3:].strip()
            if len(text) > MAX_INFER_CHARS:
                text = text[:MAX_INFER_CHARS] + "\n...[truncated]"
            if len(text.strip()) > 50:
                content_samples += f"\n### {f.name}\n{text.strip()}\n"
        except Exception:
            pass

    if not content_samples:
        return None

    logger.info("Inferring domain from input content...", phase="discovery")

    try:
        user_msg = INFER_DOMAIN_USER_TEMPLATE.format(
            content_samples=content_samples,
        )
        raw = claude_client.call(
            system=INFER_DOMAIN_SYSTEM,
            user=user_msg,
            max_tokens=1000,
            use_light_model=True,
        )
        data = _parse_json(raw)
        inferred = {
            "inferred_domain": data.get("inferred_domain", "unknown"),
            "display_name": data.get("display_name", "Unknown"),
            "key_topics": data.get("key_topics", []),
            "search_terms": data.get("search_terms", []),
        }
        logger.info(
            f"Inferred domain: '{inferred['display_name']}' "
            f"({len(inferred['search_terms'])} search terms)",
            phase="discovery",
        )
        return inferred
    except Exception as e:
        logger.warn(f"Content inference failed: {e}", phase="discovery")
        return None


def _parse_json(text: str):
    """Parse JSON from Claude response, stripping markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def run_auto_discovery(domain, language, output_dir, claude_client, web_client,
                       logger, max_refs=15,
                       timeout=DISCOVERY_TIMEOUT_SECONDS,
                       input_dir="") -> DiscoveryResult:
    """Run the full auto-discovery pipeline (synchronous).

    Steps:
      0. (If domain is generic) Infer domain from input content
      1. Analyze domain with Claude Haiku
      2. Discover candidate URLs (DDG + sitemap + crawl)
      3. Evaluate and rank URLs with Claude Haiku
      4. Crawl top URLs with fallback strategies
      5. Build baseline_summary.json (compatible with P0 format)
    """
    start_time = time.time()

    def _check_timeout(step: str) -> None:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise DiscoveryTimeoutError(
                f"Discovery timed out at step '{step}' after {elapsed:.0f}s"
            )

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "references"), exist_ok=True)

    try:
        return _run_steps(
            domain, language, output_dir, claude_client,
            web_client, logger, max_refs, _check_timeout,
            input_dir=input_dir,
        )
    except DiscoveryTimeoutError as e:
        logger.warn(str(e), phase="discovery")
        return DiscoveryResult(
            success=False, output_dir=output_dir,
            discovery_metadata={"error": str(e)},
        )
    except Exception as e:
        logger.error(f"Discovery failed: {e}", phase="discovery")
        return DiscoveryResult(
            success=False, output_dir=output_dir,
            discovery_metadata={"error": str(e)},
        )


def _run_steps(domain, language, output_dir, claude_client, web_client,
               logger, max_refs, check_timeout,
               input_dir="") -> DiscoveryResult:
    """Internal: execute the 5 discovery steps."""

    # Step 0: If domain is generic, infer from content
    inferred = None
    if _is_generic_domain(domain) and input_dir:
        logger.info(
            f"Domain '{domain}' is generic — inferring from input content",
            phase="discovery",
        )
        inferred = _infer_domain_from_content(input_dir, claude_client, logger)

    # Step 1: Analyze domain
    logger.info("Step 1/5: Analyzing domain...", phase="discovery")

    if inferred and inferred.get("search_terms"):
        # Use inferred domain instead of generic name
        effective_domain = inferred["display_name"]
        analysis = DomainAnalysis(
            domain=effective_domain,
            search_queries=inferred["search_terms"],
            expected_topics=inferred.get("key_topics", []),
        )
        logger.info(
            f"Using inferred domain '{effective_domain}' with "
            f"{len(analysis.search_queries)} content-based queries",
            phase="discovery",
        )
    else:
        analysis = analyze_domain(domain, language, claude_client, logger)

    logger.info(
        f"Found {len(analysis.official_sites)} sites, "
        f"{len(analysis.search_queries)} queries",
        phase="discovery",
    )
    check_timeout("analyze")

    # Step 2: Discover URLs
    logger.info("Step 2/5: Discovering URLs...", phase="discovery")
    candidates = discover_urls(analysis, web_client, logger, max_candidates=100)

    if not candidates:
        logger.warn("No candidate URLs found", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)
    check_timeout("discover")

    # Step 3: Evaluate and rank
    logger.info("Step 3/5: Evaluating URLs...", phase="discovery")
    ranked = evaluate_urls(candidates, analysis, claude_client, logger, max_refs=max_refs)

    if not ranked:
        logger.warn("No URLs passed evaluation", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)
    check_timeout("evaluate")

    # Step 4: Crawl
    logger.info("Step 4/5: Crawling...", phase="discovery")
    crawled = smart_crawl(ranked, output_dir, web_client, logger)
    ok_refs = [r for r in crawled if r.get("status") == "success"]

    if not ok_refs:
        logger.warn("All crawls failed", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)
    check_timeout("crawl")

    # Step 5: Build baseline_summary.json
    logger.info("Step 5/5: Building baseline...", phase="discovery")
    return _build_summary(
        analysis, output_dir, ok_refs, crawled,
        candidates, ranked, claude_client, logger,
    )


def _build_summary(analysis, output_dir, ok_refs, crawled, candidates,
                   ranked, claude_client, logger) -> DiscoveryResult:
    """Build baseline_summary.json from crawled references."""
    references = []
    for ref in ok_refs:
        try:
            with open(ref["path"], "r", encoding="utf-8") as f:
                references.append({"path": ref["path"], "content": f.read()})
        except Exception:
            pass

    total_tokens = int(sum(r.get("word_count", 0) * 1.3 for r in ok_refs))
    score = min(95.0, 60.0 + len(ok_refs) * 2.5)

    metadata = {
        "method": "auto-discovery",
        "candidates_found": len(candidates),
        "evaluated": len(ranked),
        "crawled_ok": len(ok_refs),
        "crawled_fail": len(crawled) - len(ok_refs),
        "official_sites": analysis.official_sites,
        "search_queries": analysis.search_queries,
    }

    summary = {
        "source": "auto-discovery",
        "domain": analysis.domain,
        "skill_md": "",
        "references": references,
        "topics": analysis.expected_topics,
        "total_tokens": total_tokens,
        "score": score,
        "discovery_metadata": metadata,
    }

    summary_path = os.path.join(output_dir, "baseline_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(
        f"Discovery complete: {len(ok_refs)} refs, "
        f"{len(analysis.expected_topics)} topics",
        phase="discovery",
    )

    # Report cost
    cost = getattr(claude_client, "total_cost_usd", 0.0)
    tokens = getattr(claude_client, "total_input_tokens", 0) + getattr(
        claude_client, "total_output_tokens", 0,
    )
    logger.report_cost(cost, tokens)

    return DiscoveryResult(
        success=True,
        output_dir=output_dir,
        refs_count=len(ok_refs),
        topics_count=len(analysis.expected_topics),
        total_cost_usd=cost,
        discovery_metadata=metadata,
    )
