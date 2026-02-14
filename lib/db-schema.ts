import type Database from "better-sqlite3";

export function initializeSchema(db: Database.Database) {
  db.exec(`
    CREATE TABLE IF NOT EXISTS builds (
      id              TEXT PRIMARY KEY,
      name            TEXT NOT NULL,
      domain          TEXT,
      status          TEXT NOT NULL DEFAULT 'pending',
      current_phase   TEXT,
      phase_progress  INTEGER DEFAULT 0,
      config_yaml     TEXT NOT NULL,
      template_id     TEXT,
      quality_score   REAL,
      atoms_extracted INTEGER,
      atoms_deduplicated INTEGER,
      atoms_verified  INTEGER,
      compression_ratio REAL,
      api_cost_usd    REAL DEFAULT 0,
      tokens_used     INTEGER DEFAULT 0,
      output_path     TEXT,
      package_path    TEXT,
      created_by      TEXT DEFAULT 'system',
      created_at      TEXT DEFAULT (datetime('now')),
      started_at      TEXT,
      completed_at    TEXT,
      error_message   TEXT,
      review_status   TEXT DEFAULT 'none',
      review_data     TEXT
    );

    CREATE TABLE IF NOT EXISTS build_logs (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      build_id   TEXT NOT NULL,
      timestamp  TEXT DEFAULT (datetime('now')),
      level      TEXT DEFAULT 'info',
      phase      TEXT,
      message    TEXT NOT NULL,
      metadata   TEXT,
      FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_build_logs_build
      ON build_logs(build_id, timestamp);

    CREATE TABLE IF NOT EXISTS templates (
      id          TEXT PRIMARY KEY,
      name        TEXT NOT NULL,
      domain      TEXT NOT NULL,
      description TEXT,
      icon        TEXT DEFAULT '📄',
      config_yaml TEXT NOT NULL,
      is_default  INTEGER DEFAULT 0,
      usage_count INTEGER DEFAULT 0,
      created_at  TEXT DEFAULT (datetime('now')),
      updated_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS settings (
      key         TEXT PRIMARY KEY,
      value       TEXT NOT NULL,
      description TEXT,
      updated_at  TEXT DEFAULT (datetime('now'))
    );
  `);

  // Seed settings if empty
  const settingsCount = db
    .prepare("SELECT COUNT(*) as count FROM settings")
    .get() as { count: number };
  if (settingsCount.count === 0) {
    const insertSetting = db.prepare(
      "INSERT INTO settings (key, value, description) VALUES (?, ?, ?)"
    );
    const seedSettings = db.transaction(() => {
      insertSetting.run("max_concurrent_builds", "2", "Max builds running simultaneously");
      insertSetting.run("auto_cleanup_days", "30", "Delete build logs older than N days");
      insertSetting.run("python_path", process.env.PYTHON_PATH || "py", "Python executable path");
      insertSetting.run("pipeline_path", process.env.PIPELINE_PATH || "./pipeline", "Pipeline CLI directory");
      insertSetting.run("default_quality_tier", "standard", "Default quality: draft|standard|premium");
      insertSetting.run("notification_telegram_token", "", "Telegram bot token");
      insertSetting.run("notification_telegram_chat_id", "", "Telegram chat ID");
    });
    seedSettings();
  }

  // Seed templates if empty
  const templateCount = db
    .prepare("SELECT COUNT(*) as count FROM templates")
    .get() as { count: number };
  if (templateCount.count === 0) {
    const insertTemplate = db.prepare(
      "INSERT INTO templates (id, name, domain, description, icon, config_yaml, is_default) VALUES (?, ?, ?, ?, ?, ?, ?)"
    );
    const seedTemplates = db.transaction(() => {
      insertTemplate.run(
        "tpl-fb-ads",
        "Facebook Ads Vietnam",
        "facebook-ads",
        "Build AI skill cho quảng cáo Facebook tại thị trường Việt Nam",
        "📘",
        `name: fb-ads-vietnam\ndomain: facebook-ads\nlanguage: vi\nquality_tier: standard\nplatforms: [claude]\nbaseline_sources:\n  - url: https://developers.facebook.com/docs/marketing-api\n    type: documentation\n  - url: https://www.facebook.com/business/help\n    type: documentation`,
        1
      );
      insertTemplate.run(
        "tpl-google-ads",
        "Google Ads Basics",
        "google-ads",
        "Build AI skill cho quảng cáo Google Search & Display",
        "🔍",
        `name: google-ads-basics\ndomain: google-ads\nlanguage: vi\nquality_tier: standard\nplatforms: [claude]\nbaseline_sources:\n  - url: https://support.google.com/google-ads\n    type: documentation`,
        1
      );
      insertTemplate.run(
        "tpl-blockchain",
        "Blockchain & Web3",
        "blockchain",
        "Build AI skill cho blockchain development (Solidity, DeFi, NFT)",
        "⛓️",
        `name: blockchain-web3\ndomain: blockchain\nlanguage: vi\nquality_tier: standard\nplatforms: [claude]\nbaseline_sources:\n  - url: https://docs.soliditylang.org\n    type: documentation`,
        1
      );
      insertTemplate.run(
        "tpl-custom",
        "Custom Skill",
        "custom",
        "Template trống — tự cấu hình mọi thứ từ đầu",
        "⚡",
        `name: my-custom-skill\ndomain: custom\nlanguage: vi\nquality_tier: standard\nplatforms: [claude]\nbaseline_sources: []`,
        1
      );
    });
    seedTemplates();
  }

  // Seed demo builds for UI development
  const buildCount = db
    .prepare("SELECT COUNT(*) as count FROM builds")
    .get() as { count: number };
  if (buildCount.count === 0) {
    const insertBuild = db.prepare(`
      INSERT INTO builds (id, name, domain, status, current_phase, phase_progress,
        config_yaml, template_id, quality_score, atoms_extracted, atoms_deduplicated,
        atoms_verified, api_cost_usd, tokens_used, created_by, created_at, started_at, completed_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    const seedBuilds = db.transaction(() => {
      insertBuild.run(
        "demo-001", "FB Ads Vietnam 2025", "facebook-ads", "completed", null, 100,
        "name: fb-ads-vietnam", "tpl-fb-ads", 94.2, 487, 203, 198,
        8.50, 245000, "Boss", "2025-02-10T08:00:00Z", "2025-02-10T08:01:00Z", "2025-02-10T08:15:00Z"
      );
      insertBuild.run(
        "demo-002", "Google Ads Cơ Bản", "google-ads", "running", "p3", 63,
        "name: google-ads-basic", "tpl-google-ads", null, 312, null, null,
        5.20, 156000, "Marketing", "2025-02-11T10:00:00Z", "2025-02-11T10:01:00Z", null
      );
      insertBuild.run(
        "demo-003", "Chainlink VRF Guide", "blockchain", "queued", null, 0,
        "name: chainlink-vrf", "tpl-blockchain", null, null, null, null,
        0, 0, "Dev", "2025-02-12T14:00:00Z", null, null
      );
      insertBuild.run(
        "demo-004", "TikTok Ads Strategy", "custom", "failed", "p4", 45,
        "name: tiktok-ads", "tpl-custom", null, 256, 134, null,
        6.80, 198000, "Content", "2025-02-09T09:00:00Z", "2025-02-09T09:01:00Z", "2025-02-09T09:12:00Z"
      );
    });
    seedBuilds();
  }
}
