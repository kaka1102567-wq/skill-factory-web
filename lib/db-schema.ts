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

    CREATE TABLE IF NOT EXISTS baselines (
      id              TEXT PRIMARY KEY,
      domain          TEXT NOT NULL,
      name            TEXT NOT NULL,
      config_path     TEXT,
      seekers_output_dir TEXT,
      status          TEXT NOT NULL DEFAULT 'pending',
      source_urls     TEXT,
      refs_count      INTEGER DEFAULT 0,
      topics_count    INTEGER DEFAULT 0,
      last_scraped_at TEXT,
      created_at      TEXT DEFAULT (datetime('now')),
      updated_at      TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_baselines_domain
      ON baselines(domain);
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
      insertSetting.run("claude_base_url", "", "Custom API base URL (e.g. https://claudible.io)");
      insertSetting.run("claude_model_light", "claude-haiku-4-5-20251001", "Light model for P3/P4 (cost saving)");
    });
    seedSettings();
  }

  // Ensure new settings exist (for DB upgrades)
  db.prepare(`INSERT OR IGNORE INTO settings (key, value, description) VALUES ('claude_base_url', '', 'Custom API base URL')`).run();
  db.prepare(`INSERT OR IGNORE INTO settings (key, value, description) VALUES ('claude_model_light', 'claude-haiku-4-5-20251001', 'Light model for P3/P4')`).run();

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
        `name: fb-ads-vietnam\ndomain: facebook-ads\nlanguage: vi\nquality_tier: standard\nplatforms:\n  - claude\n  - openclaw\n  - antigravity\ntranscript_paths: []\noutput_dir: "./output"\nseekers_output_dir: "output/fb-ads-meta/"\nclaude_model: "claude-sonnet-4-5-20250929"\nbaseline_sources:\n  - url: https://developers.facebook.com/docs/marketing-api\n    type: documentation\n  - url: https://www.facebook.com/business/help\n    type: documentation`,
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

  // Seed baselines if empty
  const baselineCount = db
    .prepare("SELECT COUNT(*) as count FROM baselines")
    .get() as { count: number };
  if (baselineCount.count === 0) {
    const insertBaseline = db.prepare(
      "INSERT INTO baselines (id, domain, name, config_path, seekers_output_dir, status, source_urls, refs_count, topics_count, last_scraped_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    );
    const seedBaselines = db.transaction(() => {
      insertBaseline.run(
        "bl-fb-ads", "facebook-ads", "Facebook Ads & Marketing API",
        "configs/seekers/meta_ads.json", "output/fb-ads-meta/",
        "ready",
        JSON.stringify(["https://www.facebook.com/business/help", "https://developers.facebook.com/docs/marketing-api"]),
        12, 11, new Date().toISOString()
      );
      insertBaseline.run(
        "bl-google-ads", "google-ads", "Google Ads Help Center",
        "configs/seekers/google_ads.json", null,
        "pending",
        JSON.stringify(["https://support.google.com/google-ads"]),
        0, 0, null
      );
      insertBaseline.run(
        "bl-seo", "seo", "Google Search / SEO Documentation",
        "configs/seekers/seo.json", null,
        "pending",
        JSON.stringify(["https://developers.google.com/search/docs"]),
        0, 0, null
      );
      insertBaseline.run(
        "bl-blockchain", "blockchain", "Solidity & Blockchain Dev",
        "configs/seekers/blockchain.json", null,
        "pending",
        JSON.stringify(["https://docs.soliditylang.org"]),
        0, 0, null
      );
    });
    seedBaselines();
  }

}
