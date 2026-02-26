"""Auto-Discovery Orchestrator — entry point for the full auto-discovery pipeline."""

import json
import os
import re
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
MAX_INFER_FILES = 5
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
    """Read input files (and PDF file names) to infer the real domain/topic.

    Scans input_dir for:
    - .md/.txt files: reads content samples (up to MAX_INFER_FILES)
    - .pdf files: reads FILE NAMES only (very informative for chapter titles)

    Returns dict with inferred_domain, display_name, key_topics, search_terms
    or None if inference fails.
    """
    from ..prompts.p0_discover_prompts import (
        INFER_DOMAIN_SYSTEM, INFER_DOMAIN_USER_TEMPLATE,
    )

    input_path = Path(input_dir)
    if not input_path.is_dir():
        return None

    # Collect PDF file names (available even before extraction)
    pdf_names = sorted(
        f.name for f in input_path.iterdir()
        if f.suffix.lower() == ".pdf" and f.is_file()
    )

    text_files = sorted(
        f for f in input_path.iterdir()
        if f.suffix in (".md", ".txt") and f.is_file()
    )

    # Need at least some signal: either text files or PDF names
    if not text_files and not pdf_names:
        return None

    # Build file names list (PDFs are especially informative)
    file_names = ""
    if pdf_names:
        file_names = "\n".join(f"- {name}" for name in pdf_names)
    elif text_files:
        file_names = "\n".join(f"- {f.name}" for f in text_files[:MAX_INFER_FILES])

    # Read text content samples (may be empty if only PDFs exist)
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

    logger.info(
        f"Dang suy luan chu de tu noi dung input ({len(pdf_names)} PDF, "
        f"{len(text_files)} text files)...",
        phase="discovery",
    )

    try:
        user_msg = INFER_DOMAIN_USER_TEMPLATE.format(
            file_names=file_names,
            content_samples=content_samples or "(Chua co noi dung text — chi co ten file)",
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
            f"Xac dinh chu de: '{inferred['display_name']}' — "
            f"{len(inferred['key_topics'])} chu de, "
            f"{len(inferred['search_terms'])} cau tim kiem",
            phase="discovery",
        )
        return inferred
    except Exception as e:
        logger.warn(f"Suy luan chu de that bai: {e}", phase="discovery")
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
        result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            raise
    # Unwrap list — Claude sometimes returns [{...}] instead of {...}
    if isinstance(result, list) and len(result) > 0:
        result = result[0]
    return result


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
        logger.error(f"Kham pha that bai: {e}", phase="discovery")
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
            f"Domain '{domain}' qua chung — phan tich noi dung input de xac dinh chu de that",
            phase="discovery",
        )
        inferred = _infer_domain_from_content(input_dir, claude_client, logger)

    # Step 1: Analyze domain
    logger.info("Buoc 1/5: Phan tich linh vuc...", phase="discovery")

    if inferred and inferred.get("search_terms"):
        # Use inferred domain instead of generic name
        effective_domain = inferred["display_name"]
        analysis = DomainAnalysis(
            domain=effective_domain,
            search_queries=inferred["search_terms"],
            expected_topics=inferred.get("key_topics", []),
        )
        logger.info(
            f"Su dung chu de suy luan '{effective_domain}' voi "
            f"{len(analysis.search_queries)} cau tim kiem tu noi dung",
            phase="discovery",
        )
    elif _is_generic_domain(domain):
        # Generic domain + inference failed → ABORT discovery
        # Let _maybeDiscoverFromContent (runs AFTER PDF extraction) handle it
        logger.warn(
            f"Domain '{domain}' qua chung va khong suy luan duoc chu de "
            f"(chua co file .md/.txt trong input?) — huy kham pha. "
            f"Kham pha dua tren noi dung se thu lai sau tien xu ly.",
            phase="discovery",
        )
        return DiscoveryResult(
            success=False, output_dir=output_dir,
            discovery_metadata={
                "error": "generic_domain_no_content",
                "domain": domain,
            },
        )
    else:
        analysis = analyze_domain(domain, language, claude_client, logger)

    logger.info(
        f"Tim thay {len(analysis.official_sites)} trang, "
        f"{len(analysis.search_queries)} truy van",
        phase="discovery",
    )
    check_timeout("analyze")

    # Step 2: Discover URLs
    logger.info("Buoc 2/5: Tim kiem URL...", phase="discovery")
    candidates = discover_urls(analysis, web_client, logger, max_candidates=100)

    if not candidates:
        logger.warn("Khong tim thay URL ung vien nao", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)
    check_timeout("discover")

    # Step 3: Evaluate and rank
    logger.info("Buoc 3/5: Danh gia URL...", phase="discovery")
    ranked = evaluate_urls(candidates, analysis, claude_client, logger, max_refs=max_refs)

    if not ranked:
        logger.warn("Khong co URL nao dat yeu cau danh gia", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)
    check_timeout("evaluate")

    # Step 4: Crawl
    logger.info("Buoc 4/5: Dang crawl...", phase="discovery")
    crawled = smart_crawl(ranked, output_dir, web_client, logger)
    ok_refs = [r for r in crawled if r.get("status") == "success"]

    if not ok_refs:
        logger.warn("Tat ca crawl deu that bai", phase="discovery")
        return DiscoveryResult(success=False, output_dir=output_dir)
    check_timeout("crawl")

    # Step 5: Build baseline_summary.json
    logger.info("Buoc 5/5: Tao baseline...", phase="discovery")
    return _build_summary(
        analysis, output_dir, ok_refs, crawled,
        candidates, ranked, claude_client, logger,
    )


def _score_refs_quality(
    references: list[dict], expected_topics: list[str],
) -> float:
    """Score reference quality by content depth and relevance (no Claude API)."""
    if not references:
        return 30.0

    # Content depth: refs with 200+ words of content
    good_depth = sum(
        1 for r in references
        if len(r.get("content", "").split()) >= 200
    )
    depth_score = (good_depth / len(references)) * 100

    # Relevance: refs contain expected topic keywords
    if expected_topics:
        topic_kw = set()
        for t in expected_topics[:10]:
            topic_kw.update(
                w.lower() for w in re.findall(r'\b\w{4,}\b', t)
            )
        topic_kw -= {
            'the', 'and', 'for', 'with', 'this', 'that', 'from',
            'các', 'của', 'cho', 'với', 'trong', 'được', 'không',
        }

        if topic_kw:
            refs_relevant = 0
            for r in references:
                content_lower = r.get("content", "").lower()
                hits = sum(1 for kw in topic_kw if kw in content_lower)
                if hits >= 2:
                    refs_relevant += 1
            relevance_score = (refs_relevant / len(references)) * 100
        else:
            relevance_score = 50.0
    else:
        relevance_score = 50.0

    # Refs count bonus (mild): having more refs is slightly better
    count_bonus = min(15.0, len(references) * 1.5)

    score = depth_score * 0.45 + relevance_score * 0.45 + count_bonus
    return min(95.0, max(20.0, score))


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
    score = _score_refs_quality(references, analysis.expected_topics)

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
        f"Kham pha hoan tat: {len(ok_refs)} tai lieu, "
        f"{len(analysis.expected_topics)} chu de",
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
