import Database from "better-sqlite3";
import path from "path";
import { initializeSchema } from "./db-schema";
import type { Build, BuildLog, Template, BuildStatus, PhaseId, DashboardStats } from "@/types/build";

const DB_PATH = path.join(process.cwd(), "data", "skill-factory.db");

let db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma("journal_mode = WAL");
    db.pragma("foreign_keys = ON");
    initializeSchema(db);
  }
  return db;
}

// ─── Builds ────────────────────────────────────────────

export function getBuild(id: string): Build | null {
  return getDb().prepare("SELECT * FROM builds WHERE id = ?").get(id) as Build | null;
}

export function getBuilds(status?: string): Build[] {
  const db = getDb();
  if (status && status !== "all") {
    return db.prepare("SELECT * FROM builds WHERE status = ? ORDER BY created_at DESC").all(status) as Build[];
  }
  return db.prepare("SELECT * FROM builds ORDER BY created_at DESC").all() as Build[];
}

export function createBuild(build: {
  id: string;
  name: string;
  domain: string | null;
  config_yaml: string;
  template_id: string | null;
  created_by: string;
}): Build {
  const db = getDb();
  db.prepare(`
    INSERT INTO builds (id, name, domain, status, config_yaml, template_id, created_by)
    VALUES (?, ?, ?, 'pending', ?, ?, ?)
  `).run(build.id, build.name, build.domain, build.config_yaml, build.template_id, build.created_by);
  return getBuild(build.id)!;
}

export function updateBuild(id: string, updates: Partial<{
  status: BuildStatus;
  current_phase: PhaseId | null;
  phase_progress: number;
  quality_score: number;
  atoms_extracted: number;
  atoms_deduplicated: number;
  atoms_verified: number;
  compression_ratio: number;
  api_cost_usd: number;
  tokens_used: number;
  output_path: string;
  package_path: string;
  started_at: string;
  completed_at: string;
  error_message: string | null;
  review_status: string;
  review_data: string;
}>): void {
  const db = getDb();
  const setClauses: string[] = [];
  const values: unknown[] = [];

  for (const [key, value] of Object.entries(updates)) {
    setClauses.push(`${key} = ?`);
    values.push(value);
  }

  if (setClauses.length === 0) return;
  values.push(id);

  db.prepare(`UPDATE builds SET ${setClauses.join(", ")} WHERE id = ?`).run(...values);
}

export function deleteBuild(id: string): void {
  const db = getDb();
  db.prepare("DELETE FROM build_logs WHERE build_id = ?").run(id);
  db.prepare("DELETE FROM builds WHERE id = ?").run(id);
}

// ─── Build Logs ────────────────────────────────────────

export function insertBuildLog(buildId: string, log: {
  level?: string;
  phase?: string | null;
  message: string;
  metadata?: string | null;
}): BuildLog {
  const db = getDb();
  const result = db.prepare(`
    INSERT INTO build_logs (build_id, level, phase, message, metadata)
    VALUES (?, ?, ?, ?, ?)
  `).run(buildId, log.level || "info", log.phase || null, log.message, log.metadata || null);

  return db.prepare("SELECT * FROM build_logs WHERE id = ?").get(result.lastInsertRowid) as BuildLog;
}

export function getBuildLogs(buildId: string, limit: number = 500): BuildLog[] {
  return getDb().prepare(
    "SELECT * FROM build_logs WHERE build_id = ? ORDER BY id ASC LIMIT ?"
  ).all(buildId, limit) as BuildLog[];
}

export function getBuildLogsSince(buildId: string, afterId: number): BuildLog[] {
  return getDb().prepare(
    "SELECT * FROM build_logs WHERE build_id = ? AND id > ? ORDER BY id ASC"
  ).all(buildId, afterId) as BuildLog[];
}

// ─── Templates ─────────────────────────────────────────

export function getTemplates(): Template[] {
  return getDb().prepare(
    "SELECT * FROM templates ORDER BY is_default DESC, usage_count DESC"
  ).all() as Template[];
}

export function getTemplate(id: string): Template | null {
  return getDb().prepare("SELECT * FROM templates WHERE id = ?").get(id) as Template | null;
}

export function incrementTemplateUsage(id: string): void {
  getDb().prepare("UPDATE templates SET usage_count = usage_count + 1 WHERE id = ?").run(id);
}

// ─── Settings ──────────────────────────────────────────

export function getSetting(key: string): string {
  const row = getDb().prepare("SELECT value FROM settings WHERE key = ?").get(key) as { value: string } | undefined;
  return row?.value || "";
}

export function setSetting(key: string, value: string): void {
  getDb().prepare(
    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))"
  ).run(key, value);
}

export function getAllSettings(): Record<string, string> {
  const rows = getDb().prepare("SELECT key, value FROM settings").all() as { key: string; value: string }[];
  return Object.fromEntries(rows.map(r => [r.key, r.value]));
}

// ─── Baselines ──────────────────────────────────────────

export interface Baseline {
  id: string;
  domain: string;
  name: string;
  config_path: string | null;
  seekers_output_dir: string | null;
  status: string;
  source_urls: string | null;
  refs_count: number;
  topics_count: number;
  last_scraped_at: string | null;
  created_at: string;
  updated_at: string;
}

export function getBaselines(domain?: string): Baseline[] {
  const db = getDb();
  if (domain) {
    return db.prepare("SELECT * FROM baselines WHERE domain = ? ORDER BY updated_at DESC").all(domain) as Baseline[];
  }
  return db.prepare("SELECT * FROM baselines ORDER BY updated_at DESC").all() as Baseline[];
}

export function getBaseline(id: string): Baseline | null {
  return getDb().prepare("SELECT * FROM baselines WHERE id = ?").get(id) as Baseline | null;
}

export function createBaseline(baseline: {
  id: string;
  domain: string;
  name: string;
  config_path?: string;
  seekers_output_dir?: string;
  source_urls?: string[];
}): Baseline {
  const db = getDb();
  db.prepare(`
    INSERT INTO baselines (id, domain, name, config_path, seekers_output_dir, status, source_urls)
    VALUES (?, ?, ?, ?, ?, 'pending', ?)
  `).run(
    baseline.id, baseline.domain, baseline.name,
    baseline.config_path || null,
    baseline.seekers_output_dir || null,
    baseline.source_urls ? JSON.stringify(baseline.source_urls) : null,
  );
  return getBaseline(baseline.id)!;
}

export function updateBaseline(id: string, updates: Partial<{
  name: string;
  config_path: string;
  seekers_output_dir: string;
  status: string;
  source_urls: string;
  refs_count: number;
  topics_count: number;
  last_scraped_at: string;
}>): void {
  const db = getDb();
  const setClauses: string[] = ["updated_at = datetime('now')"];
  const values: unknown[] = [];

  for (const [key, value] of Object.entries(updates)) {
    setClauses.push(`${key} = ?`);
    values.push(value);
  }

  values.push(id);
  db.prepare(`UPDATE baselines SET ${setClauses.join(", ")} WHERE id = ?`).run(...values);
}

export function deleteBaseline(id: string): void {
  getDb().prepare("DELETE FROM baselines WHERE id = ?").run(id);
}

// ─── Stats ─────────────────────────────────────────────

export function getDashboardStats(): DashboardStats {
  return getDb().prepare(`
    SELECT
      COUNT(*) as total_builds,
      SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_builds,
      ROUND(AVG(CASE WHEN quality_score IS NOT NULL THEN quality_score END), 1) as avg_quality,
      COALESCE(SUM(CASE WHEN atoms_verified IS NOT NULL THEN atoms_verified ELSE atoms_extracted END), 0) as total_atoms,
      ROUND(COALESCE(SUM(api_cost_usd), 0), 2) as total_cost,
      SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_builds
    FROM builds
  `).get() as DashboardStats;
}
