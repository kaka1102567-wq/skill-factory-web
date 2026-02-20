"""CLI command: discover-from-content — Analyze input content and auto-build baseline.

Reads sample .md files from input directory, uses Claude to analyze content,
searches DuckDuckGo for reference documentation, fetches top URLs, and creates
a baseline_summary.json compatible with P0 baseline format.

Usage:
  cli.py discover-from-content --input-dir ./input --output-dir ./baseline \
    --api-key KEY [--base-url URL] [--model MODEL] [--model-light MODEL]
"""

import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus, urlparse, unquote, parse_qs

from ..prompts.p0_discover_prompts import (
    SYSTEM_ANALYZE_CONTENT, USER_ANALYZE_CONTENT,
    SYSTEM_EVALUATE_URLS, USER_EVALUATE_URLS,
)


MAX_SAMPLE_FILES = 5
MAX_CHARS_PER_FILE = 3000
MAX_SEARCH_RESULTS = 10
MAX_REFS = 10
MAX_CONTENT_LENGTH = 30_000


def _log(level: str, message: str) -> None:
    """Print JSON log line to stdout."""
    print(json.dumps({
        "event": "log", "level": level,
        "phase": "discovery", "message": message,
    }, ensure_ascii=False), flush=True)


# ── Step 1: Read Samples ────────────────────────────────

def read_samples(input_dir: str) -> list[dict]:
    """Read first N .md files from input directory, sampling content.

    Returns list of {"filename": str, "content": str (truncated)}.
    """
    input_path = Path(input_dir)
    if not input_path.is_dir():
        return []

    md_files = sorted(input_path.glob("*.md"))
    if not md_files:
        return []

    samples = []
    for f in md_files[:MAX_SAMPLE_FILES]:
        try:
            text = f.read_text(encoding="utf-8")
            # Strip YAML frontmatter
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    text = text[end + 3:].strip()
            # Truncate
            if len(text) > MAX_CHARS_PER_FILE:
                text = text[:MAX_CHARS_PER_FILE] + "\n...[truncated]"
            if len(text.strip()) > 50:
                samples.append({"filename": f.name, "content": text.strip()})
        except Exception:
            pass

    return samples


# ── Step 2: Analyze Content ─────────────────────────────

def analyze_content(samples: list[dict], claude_client, logger=None) -> dict:
    """Use Claude Haiku to analyze sample content → domain, topics, queries.

    Returns dict with keys: domain, language, topics, search_queries,
    official_sites, content_type.
    On failure returns defaults.
    """
    samples_text = ""
    for s in samples:
        samples_text += f"\n### {s['filename']}\n{s['content']}\n"

    if logger:
        logger.info(f"Analyzing {len(samples)} samples with Claude...", phase="discovery")

    user_msg = USER_ANALYZE_CONTENT.format(samples_text=samples_text)

    try:
        raw = claude_client.call(
            system=SYSTEM_ANALYZE_CONTENT,
            user=user_msg,
            max_tokens=2000,
            use_light_model=True,
            phase="discovery",
        )
        data = _parse_json(raw)
        result = {
            "domain": data.get("domain", "unknown"),
            "language": data.get("language", "en"),
            "topics": data.get("topics", []),
            "search_queries": data.get("search_queries", []),
            "official_sites": data.get("official_sites", []),
            "content_type": data.get("content_type", "mixed"),
        }
        if logger:
            logger.info(
                f"Content analysis: domain='{result['domain']}', "
                f"{len(result['topics'])} topics, {len(result['search_queries'])} queries",
                phase="discovery",
            )
        return result
    except Exception as e:
        if logger:
            logger.warn(f"Content analysis failed: {e}, using defaults", phase="discovery")
        # Extract basic info from first sample filename
        domain = "unknown"
        if samples:
            domain = samples[0]["filename"].replace(".md", "").replace("_", " ")
        return {
            "domain": domain,
            "language": "en",
            "topics": [],
            "search_queries": [f"{domain} official documentation", f"{domain} guide"],
            "official_sites": [],
            "content_type": "mixed",
        }


# ── Step 3: Web Search (DuckDuckGo) ────────────────────

def search_ddg(queries: list[str], web_client, logger=None) -> list[dict]:
    """Search DuckDuckGo HTML for each query. Returns list of URL candidates.

    Each result: {"url": str, "title": str, "snippet": str}.
    """
    candidates = []
    seen_urls = set()

    for query in queries[:6]:
        try:
            results = _ddg_search(query, web_client)
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    candidates.append(r)
            if logger:
                logger.info(f"DDG '{query}': {len(results)} results", phase="discovery")
        except Exception as e:
            if logger:
                logger.warn(f"DDG search failed for '{query}': {e}", phase="discovery")

    if logger:
        logger.info(f"Total unique URL candidates: {len(candidates)}", phase="discovery")

    return candidates[:50]


def _ddg_search(query: str, web_client) -> list[dict]:
    """GET DuckDuckGo HTML search (no API key needed)."""
    encoded = quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    try:
        html = web_client.get(url)
    except Exception:
        return []

    results = []
    link_re = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL,
    )
    snippet_re = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL,
    )

    links = link_re.findall(html)
    snippets = snippet_re.findall(html)

    for i, (href, title_html) in enumerate(links[:MAX_SEARCH_RESULTS]):
        actual_url = _extract_ddg_url(href)
        if actual_url and _is_valid_url(actual_url):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append({
                "url": actual_url,
                "title": re.sub(r'<[^>]+>', '', title_html).strip(),
                "snippet": re.sub(r'<[^>]+>', '', snippet).strip(),
            })

    return results


def _extract_ddg_url(href: str) -> str:
    """Extract actual URL from DuckDuckGo redirect."""
    if "uddg=" in href:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return unquote(params["uddg"][0])
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return ""


_EXCLUDE_PATTERNS = [
    "/login", "/signup", "/register", "/cart", "/checkout",
    "/search?", "#comment", "/privacy", "/terms",
    "accounts.google", "facebook.com/login",
    ".zip", ".exe", "youtube.com/watch",
]


def _is_valid_url(url: str) -> bool:
    """Filter out non-documentation URLs."""
    lower = url.lower()
    return not any(x in lower for x in _EXCLUDE_PATTERNS)


# ── Step 4: Evaluate & Fetch URLs ──────────────────────

def evaluate_urls(
    candidates: list[dict], domain: str, topics: list[str],
    claude_client, logger=None,
) -> list[dict]:
    """Use Claude Haiku to score URL relevance. Returns top URLs sorted by score."""
    if not candidates:
        return []

    urls_text = ""
    for i, c in enumerate(candidates[:30]):
        urls_text += f"{i+1}. {c['url']}\n   Title: {c['title']}\n   Snippet: {c['snippet']}\n\n"

    topics_str = ", ".join(topics[:15])
    user_msg = USER_EVALUATE_URLS.format(
        domain=domain, topics=topics_str, urls_text=urls_text,
    )

    try:
        raw = claude_client.call(
            system=SYSTEM_EVALUATE_URLS,
            user=user_msg,
            max_tokens=2000,
            use_light_model=True,
            phase="discovery",
        )
        scored = _parse_json(raw)
        if not isinstance(scored, list):
            scored = scored.get("urls", scored.get("results", []))

        # Sort by score descending
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        top = scored[:MAX_REFS]

        if logger:
            logger.info(f"Evaluated: {len(scored)} URLs, top {len(top)} selected", phase="discovery")

        return top
    except Exception as e:
        if logger:
            logger.warn(f"URL evaluation failed: {e}, using all candidates", phase="discovery")
        # Fallback: return first N candidates without scoring
        return [{"url": c["url"], "score": 50} for c in candidates[:MAX_REFS]]


def fetch_references(
    urls: list[dict], output_dir: str, web_client, logger=None,
) -> list[dict]:
    """Fetch top URLs and save as markdown. Returns list of references.

    Each reference: {"path": str, "content": str, "url": str, "tokens": int}.
    """
    from ..commands.fetch_urls import fetch_and_convert

    refs_dir = os.path.join(output_dir, "references")
    os.makedirs(refs_dir, exist_ok=True)

    references = []
    for i, item in enumerate(urls):
        url = item.get("url", "")
        if not url:
            continue

        if logger:
            logger.info(f"Fetching {i+1}/{len(urls)}: {url}", phase="discovery")

        try:
            content, title = fetch_and_convert(url, web_client)
            if not content:
                continue

            # Truncate very long content
            if len(content) > MAX_CONTENT_LENGTH:
                content = content[:MAX_CONTENT_LENGTH] + "\n\n*[Truncated]*"

            domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
            filename = f"ref_{i+1:03d}_{domain}.md"
            filepath = os.path.join(refs_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {title or 'Reference'}\n\nSource: {url}\n\n{content}")

            tokens = len(content) // 4  # rough estimate
            references.append({
                "path": filepath,
                "content": content,
                "url": url,
                "tokens": tokens,
            })
        except Exception as e:
            if logger:
                logger.warn(f"Failed to fetch {url}: {e}", phase="discovery")

    if logger:
        logger.info(f"Fetched {len(references)}/{len(urls)} references", phase="discovery")

    return references


# ── Step 5: Build baseline_summary.json ────────────────

def build_baseline_summary(
    domain: str, topics: list[str], references: list[dict],
    output_dir: str, metadata: dict | None = None,
) -> str:
    """Create baseline_summary.json compatible with P0 baseline format.

    Returns path to the created file.
    """
    total_tokens = sum(r.get("tokens", 0) for r in references)
    score = min(95.0, 60.0 + len(references) * 3.0)

    summary = {
        "source": "auto-discovery-content",
        "domain": domain,
        "skill_md": "",
        "references": [
            {"path": r["path"], "content": r["content"]}
            for r in references
        ],
        "topics": topics,
        "total_tokens": total_tokens,
        "score": score,
        "discovery_metadata": {
            "method": "content-analysis",
            "refs_fetched": len(references),
            **(metadata or {}),
        },
    }

    os.makedirs(output_dir, exist_ok=True)
    summary_path = os.path.join(output_dir, "baseline_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary_path


# ── Orchestrator ────────────────────────────────────────

def run_discover_from_content(
    input_dir: str, output_dir: str,
    claude_client, web_client, logger=None,
) -> dict:
    """Main entry: analyze input content → search → fetch → baseline.

    Returns {"success": bool, "summary_path": str, "refs_count": int, ...}.
    Never raises — returns success=False on failure.
    """
    result = {"success": False, "summary_path": "", "refs_count": 0, "domain": ""}

    try:
        # Step 1: Read samples
        _log("info", "Step 1/5: Reading input samples...")
        samples = read_samples(input_dir)
        if not samples:
            _log("warn", "No readable .md files in input directory")
            return result

        _log("info", f"Read {len(samples)} sample files")

        # Step 2: Analyze content
        _log("info", "Step 2/5: Analyzing content...")
        analysis = analyze_content(samples, claude_client, logger)
        domain = analysis["domain"]
        result["domain"] = domain

        # Step 3: Web search
        _log("info", "Step 3/5: Searching for references...")
        queries = analysis.get("search_queries", [])
        if not queries:
            _log("warn", "No search queries generated")
            return result

        candidates = search_ddg(queries, web_client, logger)
        if not candidates:
            _log("warn", "No URL candidates found via web search")
            return result

        # Step 4: Evaluate & fetch
        _log("info", "Step 4/5: Evaluating and fetching references...")
        top_urls = evaluate_urls(candidates, domain, analysis.get("topics", []),
                                 claude_client, logger)
        references = fetch_references(top_urls, output_dir, web_client, logger)

        # Step 5: Build baseline
        _log("info", "Step 5/5: Building baseline...")
        metadata = {
            "content_type": analysis.get("content_type", "mixed"),
            "language": analysis.get("language", "en"),
            "candidates_found": len(candidates),
            "queries_used": queries,
        }
        summary_path = build_baseline_summary(
            domain, analysis.get("topics", []),
            references, output_dir, metadata,
        )

        result["success"] = True
        result["summary_path"] = summary_path
        result["refs_count"] = len(references)

        _log("info", f"Baseline created: {domain}, {len(references)} references")

        # Report cost
        cost = getattr(claude_client, "total_cost_usd", 0.0)
        tokens = getattr(claude_client, "total_input_tokens", 0) + getattr(
            claude_client, "total_output_tokens", 0,
        )
        if logger:
            logger.report_cost(cost, tokens)

    except Exception as e:
        _log("error", f"Discovery failed: {e}")

    return result


# ── CLI entry point ─────────────────────────────────────

def run_cmd(input_dir: str, output_dir: str,
            api_key: str, model: str = "", model_light: str = "",
            base_url: str = "") -> int:
    """CLI entry point for discover-from-content command.

    Returns exit code: 0 on success, 1 on failure.
    """
    from ..core.logger import PipelineLogger
    from ..clients.claude_client import ClaudeClient
    from ..clients.web_client import WebClient

    logger = PipelineLogger("discover")

    model = model or "claude-sonnet-4-5-20250929"
    model_light = model_light or "claude-haiku-4-5-20251001"

    try:
        claude = ClaudeClient(
            api_key=api_key, model=model,
            model_light=model_light,
            base_url=base_url or None,
            logger=logger,
        )
    except Exception as e:
        _log("error", f"Failed to initialize Claude client: {e}")
        return 1

    web = WebClient(rpm=10, timeout=30)

    try:
        result = run_discover_from_content(input_dir, output_dir, claude, web, logger)
    finally:
        web.close()

    if result["success"]:
        _log("info", f"Discovery complete: {result['domain']}, {result['refs_count']} refs")
        print(json.dumps({
            "event": "discover-baseline-done",
            **result,
        }, ensure_ascii=False), flush=True)
        return 0
    else:
        _log("warn", "Discovery did not produce a baseline")
        return 1


# ── Helpers ─────────────────────────────────────────────

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
