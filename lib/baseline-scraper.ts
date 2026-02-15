/**
 * Pre-pipeline baseline scraper.
 * Checks if baseline exists, spawns skill-seekers CLI if needed.
 * Scrape failures NEVER block the build pipeline.
 */

import { spawn, type ChildProcess } from "child_process";
import fs from "fs";
import path from "path";

const DOMAIN_CONFIGS: Record<string, string> = {
  "facebook-ads": "configs/seekers/meta_ads.json",
  "google-ads": "configs/seekers/google_ads.json",
  "seo": "configs/seekers/seo.json",
  "blockchain": "configs/seekers/blockchain.json",
};

/** Extract a simple scalar value from YAML content (no full parser needed). */
export function parseYamlValue(content: string, key: string): string {
  const regex = new RegExp(`^${key}:\\s*["']?(.+?)["']?\\s*$`, "m");
  const match = content.match(regex);
  return match?.[1]?.trim().replace(/^["']|["']$/g, "") || "";
}

/** Check if baseline SKILL.md exists in the given directory. */
export function baselineExists(seekersOutputDir: string): boolean {
  if (!seekersOutputDir) return false;
  return fs.existsSync(path.resolve(seekersOutputDir, "SKILL.md"));
}

/** Find seekers config JSON path for a given domain. */
export function findSeekersConfig(domain: string): string | null {
  if (!domain) return null;
  const configPath = DOMAIN_CONFIGS[domain];
  if (configPath && fs.existsSync(configPath)) return configPath;
  return null;
}

/**
 * Spawn skill-seekers CLI to scrape baseline docs.
 * Creates a temp config with output_dir overridden to seekersOutputDir.
 * Returns the ChildProcess — caller handles exit/error events.
 */
export function spawnScrape(
  seekersOutputDir: string,
  seekersConfigPath: string,
): ChildProcess {
  const original = JSON.parse(fs.readFileSync(seekersConfigPath, "utf-8"));
  const tempConfig = { ...original, output_dir: seekersOutputDir };

  fs.mkdirSync(seekersOutputDir, { recursive: true });
  const tempPath = path.join(seekersOutputDir, "_scrape_config.json");
  fs.writeFileSync(tempPath, JSON.stringify(tempConfig, null, 2));

  const proc = spawn("skill-seekers", [
    "scrape", "--config", tempPath, "--enhance",
  ], {
    cwd: process.cwd(),
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    shell: true,
  });

  // Cleanup temp config on exit
  proc.on("exit", () => {
    try { fs.unlinkSync(tempPath); } catch { /* ignore */ }
  });

  return proc;
}
