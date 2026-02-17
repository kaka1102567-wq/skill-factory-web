"""Auto-Discovery Orchestrator — entry point for the full auto-discovery pipeline."""

import json
import os
from dataclasses import dataclass, field

from .domain_analyzer import analyze_domain
from .url_discoverer import discover_urls
from .url_evaluator import evaluate_urls
from .scraper import smart_crawl


@dataclass
class DiscoveryResult:
    success: bool
    output_dir: str = ""
    refs_count: int = 0
    topics_count: int = 0
    total_cost_usd: float = 0.0
    discovery_metadata: dict = field(default_factory=dict)


def run_auto_discovery(domain, language, output_dir, claude_client, web_client,
                       logger, max_refs=15) -> DiscoveryResult:
    """Run the full auto-discovery pipeline (synchronous).

    Steps:
      1. Analyze domain with Claude Haiku
      2. Discover candidate URLs (DDG + sitemap + crawl)
      3. Evaluate and rank URLs with Claude Haiku
      4. Crawl top URLs with fallback strategies
      5. Build baseline_summary.json (compatible with P0 format)
    """
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "references"), exist_ok=True)

    # Step 1: Analyze domain
    logger.info("Step 1/5: Analyzing domain...", phase="discovery")
    analysis = analyze_domain(domain, language, claude_client, logger)
    logger.info(
        f"Found {len(analysis.official_sites)} sites, "
        f"{len(analysis.search_queries)} queries",
        phase="discovery",
    )

    # Step 2: Discover URLs
    logger.info("Step 2/5: Discovering URLs...", phase="discovery")
    candidates = discover_urls(analysis, web_client, logger, max_candidates=100)

    if not candidates:
        logger.warn("No candidate URLs found", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)

    # Step 3: Evaluate and rank
    logger.info("Step 3/5: Evaluating URLs...", phase="discovery")
    ranked = evaluate_urls(candidates, analysis, claude_client, logger, max_refs=max_refs)

    if not ranked:
        logger.warn("No URLs passed evaluation", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)

    # Step 4: Crawl
    logger.info("Step 4/5: Crawling...", phase="discovery")
    crawled = smart_crawl(ranked, output_dir, web_client, logger)
    ok_refs = [r for r in crawled if r.get("status") == "success"]

    if not ok_refs:
        logger.warn("All crawls failed", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)

    # Step 5: Build baseline_summary.json
    logger.info("Step 5/5: Building baseline...", phase="discovery")

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
        claude_client, "total_output_tokens", 0
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
