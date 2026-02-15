/**
 * Baseline registry — maps domain → baseline info.
 * Checks DB first, then verifies path exists on disk.
 */

import fs from "fs";
import path from "path";
import { getBaselines, type Baseline } from "./db";

export interface BaselineInfo {
  status: "ready" | "pending" | "none";
  domain: string;
  name: string;
  path: string;
  refs_count: number;
  source: string;
  message?: string;
}

/** Check if a baseline directory has required files (SKILL.md). */
function isBaselineReady(dir: string): boolean {
  if (!dir) return false;
  try {
    return fs.existsSync(path.resolve(dir, "SKILL.md"));
  } catch {
    return false;
  }
}

/** Count reference files in a baseline directory. */
function countRefs(dir: string): number {
  try {
    const refsDir = path.resolve(dir, "references");
    if (!fs.existsSync(refsDir)) return 0;
    return fs.readdirSync(refsDir).filter((f) => f.endsWith(".md")).length;
  } catch {
    return 0;
  }
}

/** Parse source URLs from JSON string stored in DB. */
function parseSourceLabel(sourceUrlsJson: string | null): string {
  if (!sourceUrlsJson) return "";
  try {
    const urls: string[] = JSON.parse(sourceUrlsJson);
    return urls
      .map((u) => {
        try {
          return new URL(u).hostname.replace("www.", "");
        } catch {
          return u;
        }
      })
      .join(", ");
  } catch {
    return "";
  }
}

/**
 * Get baseline info for a domain.
 * 1. Query DB baselines table for domain with status='ready' + seekers_output_dir set
 * 2. If found, verify path exists on disk
 * 3. If not ready but DB entry exists → pending
 * 4. Otherwise → none
 */
export function getBaselineForDomain(domain: string): BaselineInfo {
  if (!domain) {
    return { status: "none", domain, name: "", path: "", refs_count: 0, source: "", message: "No domain specified" };
  }

  const baselines: Baseline[] = getBaselines(domain);

  if (baselines.length > 0) {
    const bl = baselines[0];

    if (bl.status === "ready" && bl.seekers_output_dir && isBaselineReady(bl.seekers_output_dir)) {
      const refs = bl.refs_count || countRefs(bl.seekers_output_dir);
      return {
        status: "ready",
        domain: bl.domain,
        name: bl.name,
        path: bl.seekers_output_dir,
        refs_count: refs,
        source: parseSourceLabel(bl.source_urls),
      };
    }

    // DB entry exists but not ready → pending
    return {
      status: "pending",
      domain: bl.domain,
      name: bl.name,
      path: bl.seekers_output_dir || "",
      refs_count: 0,
      source: parseSourceLabel(bl.source_urls),
      message: "Baseline will be auto-scraped during build",
    };
  }

  return {
    status: "none",
    domain,
    name: "",
    path: "",
    refs_count: 0,
    source: "",
    message: "No baseline available for this domain",
  };
}
