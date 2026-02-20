import { spawn, ChildProcess } from "child_process";
import path from "path";
import fs from "fs";
import { updateBuild, insertBuildLog, getBuild, getSetting } from "./db";
import { sseManager } from "./sse-manager";
import { notifyBuildComplete } from "./notifications";
import { parseYamlValue, baselineExists, findSeekersConfig, spawnScrape } from "./baseline-scraper";
import { getBaselineForDomain } from "./baseline-registry";
import { yamlStr } from "./config-generator";
import type { PhaseId } from "@/types/build";

// Chapter detection pattern: "01 ...", "01-...", "01_...", "01. ..."
const CHAPTER_PATTERN = /^(\d{1,3})[\s._-]+(.+)\.pdf$/i;

// Track running processes globally (survives hot reload)
const globalForRunner = globalThis as unknown as { runningProcesses: Map<string, ChildProcess> };
if (!globalForRunner.runningProcesses) {
  globalForRunner.runningProcesses = new Map();
}
const runningProcesses = globalForRunner.runningProcesses;

export interface BuildConfig {
  id: string;
  name: string;
  configPath: string;
  outputDir: string;
}

export function startBuild(config: BuildConfig): ChildProcess {
  const pythonPath = getSetting("python_path") || process.env.PYTHON_PATH || "py";
  const pipelinePath = getSetting("pipeline_path") || process.env.PIPELINE_PATH || "./pipeline";

  // USE_REAL_PIPELINE toggle: 'false' → fallback to mock_cli.py
  const useReal = (process.env.USE_REAL_PIPELINE ?? "true").toLowerCase() !== "false";
  const cliScript = useReal ? "cli.py" : "mock_cli.py";
  const cliPath = path.join(pipelinePath, cliScript);

  console.log(`[BUILD] Starting build ${config.id}: ${pythonPath} ${cliPath} (real=${useReal})`);
  console.log(`[BUILD] Config: ${config.configPath}, Output: ${config.outputDir}`);

  updateBuild(config.id, {
    status: "running",
    started_at: new Date().toISOString(),
  });

  const startLog = {
    level: "info",
    phase: null,
    message: `Build started: ${config.name}`,
  };
  insertBuildLog(config.id, startLog);
  sseManager.broadcast(config.id, "log", { ...startLog, timestamp: new Date().toISOString() });

  // ─── Pre-scrape baseline if needed ──────────────────
  try {
    const configContent = fs.readFileSync(config.configPath, "utf-8");
    let seekersDir = parseYamlValue(configContent, "seekers_output_dir");
    const domain = parseYamlValue(configContent, "domain");

    // Auto-detect baseline path from registry if not set in config
    if (!seekersDir && domain) {
      const bl = getBaselineForDomain(domain);
      if (bl.status === "ready" && bl.path) {
        seekersDir = bl.path;
        const msg = `Auto-detected baseline for "${domain}": ${bl.refs_count} reference(s)`;
        insertBuildLog(config.id, { level: "info", message: msg });
        sseManager.broadcast(config.id, "log", { level: "info", message: msg, timestamp: new Date().toISOString() });
      }
    }

    const seekersConfig = seekersDir && !baselineExists(seekersDir) ? findSeekersConfig(domain) : null;

    if (seekersConfig) {
      const scrapeMsg = `Pre-scraping baseline for domain "${domain}"...`;
      insertBuildLog(config.id, { level: "info", message: scrapeMsg });
      sseManager.broadcast(config.id, "log", { level: "info", message: scrapeMsg, timestamp: new Date().toISOString() });

      const scrapeProc = spawnScrape(seekersDir, seekersConfig);
      runningProcesses.set(config.id, scrapeProc);

      scrapeProc.stdout?.on("data", (chunk: Buffer) => {
        const msg = chunk.toString().trim();
        if (msg) handlePlainLog(config.id, msg, "debug");
      });
      scrapeProc.stderr?.on("data", (chunk: Buffer) => {
        const msg = chunk.toString().trim();
        if (msg) handlePlainLog(config.id, msg, "debug");
      });

      scrapeProc.on("exit", (code) => {
        const ok = code === 0 && baselineExists(seekersDir);
        const msg = ok
          ? "Baseline scraped successfully"
          : `Baseline scrape ${code === 0 ? "produced no output" : `failed (code ${code})`}, continuing without pre-scraped baseline...`;
        insertBuildLog(config.id, { level: ok ? "info" : "warn", message: msg });
        sseManager.broadcast(config.id, "log", { level: ok ? "info" : "warn", message: msg, timestamp: new Date().toISOString() });
        _preProcessInputs(config, pythonPath, cliPath);
      });

      scrapeProc.on("error", (err) => {
        const msg = `Baseline scrape error: ${err.message}, continuing...`;
        insertBuildLog(config.id, { level: "warn", message: msg });
        sseManager.broadcast(config.id, "log", { level: "warn", message: msg, timestamp: new Date().toISOString() });
        _preProcessInputs(config, pythonPath, cliPath);
      });

      return scrapeProc;
    }
  } catch (err) {
    const msg = `Pre-scrape check failed: ${err instanceof Error ? err.message : err}, continuing...`;
    console.warn(`[BUILD] ${msg}`);
    insertBuildLog(config.id, { level: "warn", message: msg });
  }

  return _preProcessInputs(config, pythonPath, cliPath);
}

// ─── Pre-process Inputs (URLs + PDFs) before pipeline ─

function _preProcessInputs(config: BuildConfig, pythonPath: string, cliPath: string): ChildProcess {
  const configContent = fs.readFileSync(config.configPath, "utf-8");
  const buildDir = path.dirname(config.outputDir);
  const inputDir = path.join(buildDir, "input");

  // ★ Auto-Discovery: if no baseline and auto_discover_baseline enabled
  const seekersDir = parseYamlValue(configContent, "seekers_output_dir");
  const hasBaseline = !!seekersDir;
  const autoDiscover = parseYamlValue(configContent, "auto_discover_baseline") !== "false";
  const domain = parseYamlValue(configContent, "domain");
  const language = parseYamlValue(configContent, "language") || "en";

  if (!hasBaseline && autoDiscover && domain) {
    const discoveryDir = path.join(buildDir, "baseline");
    const pipelinePath = path.dirname(cliPath);
    const realCliPath = path.join(pipelinePath, "cli.py");

    const claudeApiKey = getSetting("claude_api_key") || process.env.CLAUDE_API_KEY || "";
    const claudeModel = getSetting("claude_model") || process.env.CLAUDE_MODEL || "claude-sonnet-4-5-20250929";
    const claudeModelLight = getSetting("claude_model_light") || process.env.CLAUDE_MODEL_LIGHT || "claude-haiku-4-5-20251001";
    const claudeBaseUrl = getSetting("claude_base_url") || process.env.CLAUDE_BASE_URL || "";

    if (claudeApiKey) {
      const discoverMsg = `Auto-discovering baseline for: ${domain}`;
      insertBuildLog(config.id, { level: "info", phase: null, message: discoverMsg });
      sseManager.broadcast(config.id, "log", { level: "info", phase: "discovery", message: discoverMsg, timestamp: new Date().toISOString() });

      const discoverArgs = [
        realCliPath, "discover-baseline",
        "--domain", domain,
        "--language", language,
        "--output", discoveryDir,
        "--max-refs", "15",
        "--api-key", claudeApiKey,
        "--model", claudeModel,
        "--model-light", claudeModelLight,
      ];
      if (claudeBaseUrl) discoverArgs.push("--base-url", claudeBaseUrl);

      const discoverProc = spawn(pythonPath, discoverArgs, {
        cwd: process.cwd(),
        env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
      });

      runningProcesses.set(config.id, discoverProc);

      discoverProc.stdout?.on("data", (chunk: Buffer) => {
        const text = chunk.toString().trim();
        if (text) {
          for (const line of text.split("\n")) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            try {
              const parsed = JSON.parse(trimmed);
              handleParsedLog(config.id, parsed);
              _emitDiscoveryStep(config.id, (parsed.message as string) || "");
            } catch {
              handlePlainLog(config.id, trimmed, "debug");
              _emitDiscoveryStep(config.id, trimmed);
            }
          }
        }
      });
      discoverProc.stderr?.on("data", (chunk: Buffer) => {
        const text = chunk.toString().trim();
        if (text) handlePlainLog(config.id, text, "debug");
      });

      discoverProc.on("exit", (code) => {
        const summaryPath = path.join(discoveryDir, "baseline_summary.json");
        const ok = code === 0 && fs.existsSync(summaryPath);
        const msg = ok
          ? "Auto-discovery complete — baseline ready"
          : "Auto-discovery did not find baseline — continuing without";
        insertBuildLog(config.id, { level: ok ? "info" : "warn", message: msg });
        sseManager.broadcast(config.id, "log", { level: ok ? "info" : "warn", phase: "discovery", message: msg, timestamp: new Date().toISOString() });

        // Mark all discovery steps done/failed
        for (let i = 1; i <= 5; i++) {
          sseManager.broadcast(config.id, "pre-step", {
            id: `discovery_${i}`, label: DISCOVERY_STEP_LABELS[i], status: ok ? "done" : "failed",
          });
        }

        // If discovery succeeded, update config so pipeline uses it
        if (ok) {
          try {
            const updated = configContent.replace(
              /^seekers_output_dir:.*$/m,
              `seekers_output_dir: ${yamlStr(discoveryDir)}`,
            );
            fs.writeFileSync(config.configPath, updated, "utf-8");
          } catch { /* config update failed, pipeline still runs */ }
        }

        _continuePreProcessInputs(config, pythonPath, cliPath, inputDir);
      });

      discoverProc.on("error", (err) => {
        const msg = `Auto-discovery error: ${err.message} — continuing without baseline`;
        insertBuildLog(config.id, { level: "warn", message: msg });
        sseManager.broadcast(config.id, "log", { level: "warn", phase: "discovery", message: msg, timestamp: new Date().toISOString() });
        _continuePreProcessInputs(config, pythonPath, cliPath, inputDir);
      });

      const placeholder = spawn(pythonPath, ["--version"], { stdio: "ignore" });
      return placeholder;
    }
  }

  return _continuePreProcessInputs(config, pythonPath, cliPath, inputDir);
}

const DISCOVERY_STEP_RE = /^Step (\d)\/5:\s*(.+?)\.{0,3}$/;
const DISCOVERY_STEP_LABELS: Record<number, string> = {
  1: "Analyzing domain",
  2: "Discovering URLs",
  3: "Evaluating URLs",
  4: "Crawling references",
  5: "Building baseline",
};

function _emitDiscoveryStep(buildId: string, message: string): void {
  const m = message.match(DISCOVERY_STEP_RE);
  if (!m) return;
  const step = parseInt(m[1]);
  const label = DISCOVERY_STEP_LABELS[step] || m[2];
  // Mark previous steps done, current as running
  for (let i = 1; i < step; i++) {
    sseManager.broadcast(buildId, "pre-step", {
      id: `discovery_${i}`, label: DISCOVERY_STEP_LABELS[i] || `Step ${i}`, status: "done",
    });
  }
  sseManager.broadcast(buildId, "pre-step", {
    id: `discovery_${step}`, label, status: "running",
  });
}

/** Continues pre-processing after optional auto-discovery step. */
function _continuePreProcessInputs(
  config: BuildConfig, pythonPath: string, cliPath: string, inputDir: string,
): ChildProcess {
  const configContent = fs.readFileSync(config.configPath, "utf-8");

  // Parse input_urls from config.yaml
  const urlsMatch = configContent.match(/input_urls:\s*\n((?:\s+-\s*.+\n)*)/);
  const urls: string[] = [];
  if (urlsMatch) {
    const lines = urlsMatch[1].split("\n");
    for (const line of lines) {
      const m = line.match(/^\s+-\s*["']?(.+?)["']?\s*$/);
      if (m) urls.push(m[1]);
    }
  }

  // Parse github_repo from config.yaml
  const githubRepoMatch = configContent.match(/^github_repo:\s*["']?(.+?)["']?\s*$/m);
  const githubRepo = githubRepoMatch?.[1]?.trim() || "";
  const noCodeMatch = configContent.match(/^github_analyze_code:\s*(false|no)/mi);
  const analyzeCode = !noCodeMatch;

  // Check for PDFs in input dir
  const pdfFiles: string[] = [];
  if (fs.existsSync(inputDir)) {
    for (const f of fs.readdirSync(inputDir)) {
      if (f.toLowerCase().endsWith(".pdf")) pdfFiles.push(f);
    }
  }

  const hasUrls = urls.length > 0;
  const hasPdfs = pdfFiles.length > 0;
  const hasGithub = githubRepo.length > 0;

  if (!hasUrls && !hasPdfs && !hasGithub) {
    return _spawnPipeline(config, pythonPath, cliPath);
  }

  const pipelinePath = path.dirname(cliPath);
  const realCliPath = path.join(pipelinePath, "cli.py");

  // Chain: fetch URLs → extract PDFs → spawn pipeline
  const runStep = (stepName: string, args: string[], timeoutMs: number): Promise<number> => {
    return new Promise((resolve) => {
      const msg = `Pre-processing: ${stepName}...`;
      insertBuildLog(config.id, { level: "info", phase: null, message: msg });
      sseManager.broadcast(config.id, "log", { level: "info", phase: "pre", message: msg, timestamp: new Date().toISOString() });

      const proc = spawn(pythonPath, [realCliPath, ...args], {
        cwd: process.cwd(),
        env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
      });

      const timer = setTimeout(() => { proc.kill("SIGTERM"); }, timeoutMs);

      proc.stdout?.on("data", (chunk: Buffer) => {
        const text = chunk.toString().trim();
        if (text) handlePlainLog(config.id, text, "debug");
      });
      proc.stderr?.on("data", (chunk: Buffer) => {
        const text = chunk.toString().trim();
        if (text) handlePlainLog(config.id, text, "debug");
      });
      proc.on("exit", (code) => { clearTimeout(timer); resolve(code ?? 1); });
      proc.on("error", () => { clearTimeout(timer); resolve(1); });
    });
  };

  // Run async chain, then spawn pipeline
  (async () => {
    if (hasUrls) {
      sseManager.broadcast(config.id, "pre-step", { id: "pre_urls", label: `Fetching ${urls.length} URLs`, status: "running" });
      const urlStr = urls.join(",");
      const code = await runStep(`fetching ${urls.length} URLs`, ["fetch-urls", "--urls", urlStr, "--output-dir", inputDir], 60_000);
      const lvl = code === 0 ? "info" : "warn";
      const msg = code === 0 ? `Fetched ${urls.length} URLs` : `URL fetch exited with code ${code}, continuing...`;
      insertBuildLog(config.id, { level: lvl, message: msg });
      sseManager.broadcast(config.id, "log", { level: lvl, phase: "pre", message: msg, timestamp: new Date().toISOString() });
      sseManager.broadcast(config.id, "pre-step", { id: "pre_urls", label: `Fetching ${urls.length} URLs`, status: code === 0 ? "done" : "failed" });
    }

    if (hasPdfs) {
      sseManager.broadcast(config.id, "pre-step", { id: "pre_pdfs", label: `Extracting ${pdfFiles.length} PDFs`, status: "running" });
      // OCR can take ~10s/page, 50 pages × 14 files = ~7000s worst case
      const pdfTimeout = Math.max(300_000, pdfFiles.length * 120_000);
      const code = await runStep(`extracting ${pdfFiles.length} PDFs`, ["extract-pdf", "--input-dir", inputDir, "--output-dir", inputDir], pdfTimeout);
      const lvl = code === 0 ? "info" : "warn";
      const msg = code === 0 ? `Extracted ${pdfFiles.length} PDFs` : `PDF extraction exited with code ${code}, continuing...`;
      insertBuildLog(config.id, { level: lvl, message: msg });
      sseManager.broadcast(config.id, "log", { level: lvl, phase: "pre", message: msg, timestamp: new Date().toISOString() });
      sseManager.broadcast(config.id, "pre-step", { id: "pre_pdfs", label: `Extracting ${pdfFiles.length} PDFs`, status: code === 0 ? "done" : "failed" });

      // Auto-merge chapter PDFs after extraction
      if (code === 0) {
        _detectAndMergeChapters(inputDir, pdfFiles, config.id);
      }
    }

    if (hasGithub) {
      sseManager.broadcast(config.id, "pre-step", { id: "pre_github", label: "Analyzing GitHub repo", status: "running" });
      const repoArgs = ["analyze-repo", "--repo", githubRepo, "--output-dir", inputDir];
      if (!analyzeCode) repoArgs.push("--no-code");
      const code = await runStep(`analyzing GitHub repo`, repoArgs, 180_000);
      const lvl = code === 0 ? "info" : "warn";
      const msg = code === 0
        ? "GitHub repo analysis complete"
        : `Repo analysis exited with code ${code}, continuing without code analysis...`;
      insertBuildLog(config.id, { level: lvl, message: msg });
      sseManager.broadcast(config.id, "log", { level: lvl, phase: "pre", message: msg, timestamp: new Date().toISOString() });
      sseManager.broadcast(config.id, "pre-step", { id: "pre_github", label: "Analyzing GitHub repo", status: code === 0 ? "done" : "failed" });
    }

    // ★ Content-based baseline discovery (fallback when no baseline exists)
    await _maybeDiscoverFromContent(config, pythonPath, cliPath, inputDir, runStep);

    const doneMsg = "Pre-processing complete";
    insertBuildLog(config.id, { level: "info", message: doneMsg });
    sseManager.broadcast(config.id, "log", { level: "info", phase: "pre", message: doneMsg, timestamp: new Date().toISOString() });

    _spawnPipeline(config, pythonPath, cliPath);
  })();

  // Return a placeholder process — the real pipeline will be spawned after pre-processing
  // We create a no-op child so the caller has something to track
  const placeholder = spawn(pythonPath, ["--version"], { stdio: "ignore" });
  runningProcesses.set(config.id, placeholder);
  return placeholder;
}

// ─── Content-Based Baseline Discovery ──────────────────

async function _maybeDiscoverFromContent(
  config: BuildConfig, pythonPath: string, cliPath: string, inputDir: string,
  runStep: (stepName: string, args: string[], timeoutMs: number) => Promise<number>,
): Promise<void> {
  // Re-read config to check if domain-based discovery already set a baseline
  const latestConfig = fs.readFileSync(config.configPath, "utf-8");
  const seekersDir = parseYamlValue(latestConfig, "seekers_output_dir");
  if (seekersDir) return; // baseline already configured

  // Check if baseline_sources has a .json entry
  if (latestConfig.includes("baseline_summary.json")) return;

  // Check if input dir has .md files to analyze
  if (!fs.existsSync(inputDir)) return;
  const mdFiles = fs.readdirSync(inputDir).filter(f => f.endsWith(".md"));
  if (mdFiles.length === 0) return;

  // Need API key for content analysis
  const claudeApiKey = getSetting("claude_api_key") || process.env.CLAUDE_API_KEY || "";
  if (!claudeApiKey) return;

  const claudeModel = getSetting("claude_model") || process.env.CLAUDE_MODEL || "";
  const claudeModelLight = getSetting("claude_model_light") || process.env.CLAUDE_MODEL_LIGHT || "";
  const claudeBaseUrl = getSetting("claude_base_url") || process.env.CLAUDE_BASE_URL || "";

  const buildDir = path.dirname(config.outputDir);
  const baselineDir = path.join(buildDir, "baseline");

  const discoverMsg = `Auto-discovering baseline from ${mdFiles.length} input files...`;
  insertBuildLog(config.id, { level: "info", message: discoverMsg });
  sseManager.broadcast(config.id, "log", { level: "info", phase: "discovery", message: discoverMsg, timestamp: new Date().toISOString() });
  sseManager.broadcast(config.id, "pre-step", { id: "pre_content_discover", label: "Analyzing content for baseline", status: "running" });

  const discoverArgs = [
    "discover-from-content",
    "--input-dir", inputDir,
    "--output-dir", baselineDir,
    "--api-key", claudeApiKey,
  ];
  if (claudeModel) discoverArgs.push("--model", claudeModel);
  if (claudeModelLight) discoverArgs.push("--model-light", claudeModelLight);
  if (claudeBaseUrl) discoverArgs.push("--base-url", claudeBaseUrl);

  // runStep spawns: pythonPath realCliPath ...args
  const code = await runStep("analyzing content for baseline", discoverArgs, 180_000);
  const summaryPath = path.join(baselineDir, "baseline_summary.json");
  const ok = code === 0 && fs.existsSync(summaryPath);

  const lvl = ok ? "info" : "warn";
  const msg = ok
    ? "Content-based baseline discovery complete"
    : "Content-based discovery did not produce baseline — continuing without";
  insertBuildLog(config.id, { level: lvl, message: msg });
  sseManager.broadcast(config.id, "log", { level: lvl, phase: "discovery", message: msg, timestamp: new Date().toISOString() });
  sseManager.broadcast(config.id, "pre-step", { id: "pre_content_discover", label: "Analyzing content for baseline", status: ok ? "done" : "failed" });

  // Update config so P0 uses the discovered baseline
  if (ok) {
    try {
      let updated = latestConfig;
      // Add baseline_sources with path to baseline_summary.json
      if (updated.includes("baseline_sources: []")) {
        updated = updated.replace(
          "baseline_sources: []",
          `baseline_sources:\n  - ${yamlStr(summaryPath)}`,
        );
      } else if (!updated.includes("baseline_sources:")) {
        updated += `\nbaseline_sources:\n  - ${yamlStr(summaryPath)}\n`;
      }
      fs.writeFileSync(config.configPath, updated, "utf-8");
    } catch { /* config update failed, pipeline still runs */ }
  }
}

// ─── Chapter Detection & Merge ─────────────────────────

function _detectAndMergeChapters(
  inputDir: string, pdfFiles: string[], buildId: string,
): { merged: boolean; chapterCount: number; mergedFile: string } {
  const chapters: { index: number; filename: string }[] = [];
  for (const f of pdfFiles) {
    const match = f.match(CHAPTER_PATTERN);
    if (match) chapters.push({ index: parseInt(match[1], 10), filename: f });
  }

  if (chapters.length < 2) return { merged: false, chapterCount: 0, mergedFile: "" };

  chapters.sort((a, b) => a.index - b.index);

  const mergedParts: string[] = [];
  for (const ch of chapters) {
    const txtName = ch.filename.replace(/\.pdf$/i, ".txt");
    const txtPath = path.join(inputDir, txtName);
    if (fs.existsSync(txtPath)) {
      const content = fs.readFileSync(txtPath, "utf-8").trim();
      if (content) {
        mergedParts.push(`\n--- ${ch.filename} ---\n\n${content}`);
      }
      fs.unlinkSync(txtPath);
    }
  }

  if (mergedParts.length === 0) return { merged: false, chapterCount: 0, mergedFile: "" };

  const mergedFile = "merged-chapters.txt";
  fs.writeFileSync(path.join(inputDir, mergedFile), mergedParts.join("\n\n").trim(), "utf-8");

  const msg = `Auto-merged ${chapters.length} chapter PDFs → ${mergedFile}`;
  insertBuildLog(buildId, { level: "info", message: msg });
  sseManager.broadcast(buildId, "log", {
    level: "info", phase: "pre", message: msg, timestamp: new Date().toISOString(),
  });

  return { merged: true, chapterCount: chapters.length, mergedFile };
}

// ─── Pipeline Spawn (extracted for pre-scrape chaining) ─

function _spawnPipeline(config: BuildConfig, pythonPath: string, cliPath: string): ChildProcess {
  const claudeApiKey = getSetting("claude_api_key") || process.env.CLAUDE_API_KEY || "";
  const claudeModel = getSetting("claude_model") || process.env.CLAUDE_MODEL || "claude-sonnet-4-5-20250929";
  const seekersCacheDir = getSetting("seekers_cache_dir") || process.env.SEEKERS_CACHE_DIR || "./data/cache";
  const claudeBaseUrl = getSetting("claude_base_url") || process.env.CLAUDE_BASE_URL || "";
  const claudeModelLight = getSetting("claude_model_light") || process.env.CLAUDE_MODEL_LIGHT || "claude-haiku-4-5-20251001";

  const proc = spawn(pythonPath, [
    cliPath, "build",
    "--config", config.configPath,
    "--output", config.outputDir,
    "--json-logs",
  ], {
    cwd: process.cwd(),
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      PYTHONIOENCODING: "utf-8",
      CLAUDE_API_KEY: claudeApiKey,
      CLAUDE_MODEL: claudeModel,
      SEEKERS_CACHE_DIR: seekersCacheDir,
      CLAUDE_BASE_URL: claudeBaseUrl,
      CLAUDE_MODEL_LIGHT: claudeModelLight,
    },
  });

  runningProcesses.set(config.id, proc);

  let stdoutBuffer = "";
  proc.stdout.on("data", (chunk: Buffer) => {
    stdoutBuffer += chunk.toString();
    const lines = stdoutBuffer.split("\n");
    stdoutBuffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        handleParsedLog(config.id, JSON.parse(trimmed));
      } catch {
        handlePlainLog(config.id, trimmed);
      }
    }
  });

  let stderrBuffer = "";
  proc.stderr.on("data", (chunk: Buffer) => {
    stderrBuffer += chunk.toString();
    const lines = stderrBuffer.split("\n");
    stderrBuffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      if (trimmed.includes("DeprecationWarning") || trimmed.includes("FutureWarning")) {
        handlePlainLog(config.id, trimmed, "debug");
      } else {
        handlePlainLog(config.id, trimmed, "error");
      }
    }
  });

  proc.on("exit", (code, signal) => {
    runningProcesses.delete(config.id);
    if (stdoutBuffer.trim()) handlePlainLog(config.id, stdoutBuffer.trim());
    if (stderrBuffer.trim()) handlePlainLog(config.id, stderrBuffer.trim(), "error");

    const status = code === 0 ? "completed" : "failed";
    const now = new Date().toISOString();
    console.log(`[BUILD] Build ${config.id} exited: code=${code}, signal=${signal}`);

    updateBuild(config.id, {
      status,
      completed_at: now,
      error_message: code !== 0 ? `Process exited with code ${code}${signal ? `, signal ${signal}` : ""}` : null,
    });

    const finalLog = {
      level: status === "completed" ? "info" : "error",
      message: `Build ${status}${code !== 0 ? ` (exit code: ${code})` : ""}`,
    };
    insertBuildLog(config.id, finalLog);

    const build = getBuild(config.id);
    sseManager.broadcast(config.id, "complete", {
      status,
      quality_score: build?.quality_score,
      package_path: build?.package_path,
      completed_at: now,
    });

    if (build) notifyBuildComplete(build).catch(() => {});

    const processQueue = (globalThis as Record<string, unknown>).__processQueue as (() => void) | undefined;
    if (processQueue) processQueue();
  });

  proc.on("error", (err) => {
    runningProcesses.delete(config.id);
    console.error(`[BUILD] Spawn error for ${config.id}:`, err.message);
    updateBuild(config.id, {
      status: "failed",
      completed_at: new Date().toISOString(),
      error_message: `Spawn error: ${err.message}`,
    });
    insertBuildLog(config.id, { level: "error", message: `Failed to start build: ${err.message}` });
    sseManager.broadcast(config.id, "error", { message: err.message, retryable: true });
  });

  return proc;
}

// ─── Log Handlers ──────────────────────────────────────

function handleParsedLog(buildId: string, parsed: Record<string, unknown>): void {
  const event = (parsed.event as string) || "log";
  const phase = parsed.phase as PhaseId | undefined;
  const message = (parsed.message as string) || JSON.stringify(parsed);
  const level = (parsed.level as string) || "info";
  const timestamp = new Date().toISOString();

  insertBuildLog(buildId, {
    level,
    phase: phase || null,
    message,
    metadata: JSON.stringify(parsed),
  });

  if (event === "phase" && phase) {
    const progress = (parsed.progress as number) || 0;
    const status = parsed.status as string;
    updateBuild(buildId, {
      current_phase: phase,
      phase_progress: progress,
    });
    sseManager.broadcast(buildId, "phase", {
      phase,
      name: parsed.name,
      status,
      progress,
      timestamp,
    });
  }

  if (event === "quality") {
    const score = parsed.score as number;
    const pass = parsed.pass as boolean;
    sseManager.broadcast(buildId, "quality", {
      phase,
      score,
      pass,
      atoms_count: parsed.atoms_count,
      // Include aggregate fields so frontend gets real-time updates
      quality_score: parsed.quality_score,
      atoms_extracted: parsed.atoms_extracted,
      atoms_deduplicated: parsed.atoms_deduplicated,
      atoms_verified: parsed.atoms_verified,
      timestamp,
    });

    if (parsed.atoms_extracted) updateBuild(buildId, { atoms_extracted: parsed.atoms_extracted as number });
    if (parsed.atoms_deduplicated) updateBuild(buildId, { atoms_deduplicated: parsed.atoms_deduplicated as number });
    if (parsed.atoms_verified) updateBuild(buildId, { atoms_verified: parsed.atoms_verified as number });
    if (parsed.quality_score) updateBuild(buildId, { quality_score: parsed.quality_score as number });
    if (parsed.compression_ratio) updateBuild(buildId, { compression_ratio: parsed.compression_ratio as number });
  }

  if (event === "cost" || parsed.api_cost_usd) {
    updateBuild(buildId, {
      api_cost_usd: parsed.api_cost_usd as number,
      tokens_used: (parsed.tokens_used as number) || 0,
    });
    sseManager.broadcast(buildId, "cost", {
      api_cost_usd: parsed.api_cost_usd,
      tokens_used: parsed.tokens_used,
      timestamp,
    });
  }

  if (event === "conflict" && ((parsed.count as number) || 0) > 0) {
    updateBuild(buildId, {
      status: "paused",
      review_status: "pending",
      review_data: JSON.stringify(parsed.conflicts || parsed),
    });
    sseManager.broadcast(buildId, "conflict", parsed);
  }

  if (event === "package" && parsed.path) {
    updateBuild(buildId, {
      package_path: parsed.path as string,
      output_path: (parsed.output_dir as string) || undefined,
    });
  }

  if (event === "log" || !["phase", "quality", "cost", "conflict", "package"].includes(event)) {
    sseManager.broadcast(buildId, "log", {
      level,
      phase,
      message,
      timestamp,
    });
  }
}

function handlePlainLog(buildId: string, message: string, level: string = "info"): void {
  insertBuildLog(buildId, { level, message });
  sseManager.broadcast(buildId, "log", {
    level,
    message,
    timestamp: new Date().toISOString(),
  });
}

// ─── Resume After Conflict Resolution ─────────────────

export interface ResolveConfig {
  id: string;
  name: string;
  outputDir: string;
  resolutionsPath: string;
}

export function resumeAfterResolve(config: ResolveConfig): ChildProcess {
  const pythonPath = getSetting("python_path") || process.env.PYTHON_PATH || "py";
  const pipelinePath = getSetting("pipeline_path") || process.env.PIPELINE_PATH || "./pipeline";
  const useReal = (process.env.USE_REAL_PIPELINE ?? "true").toLowerCase() !== "false";
  const cliPath = path.join(pipelinePath, useReal ? "cli.py" : "mock_cli.py");

  const claudeApiKey = getSetting("claude_api_key") || process.env.CLAUDE_API_KEY || "";
  const claudeModel = getSetting("claude_model") || process.env.CLAUDE_MODEL || "claude-sonnet-4-5-20250929";
  const seekersCacheDir = getSetting("seekers_cache_dir") || process.env.SEEKERS_CACHE_DIR || "./data/cache";
  const claudeBaseUrl = getSetting("claude_base_url") || process.env.CLAUDE_BASE_URL || "";
  const claudeModelLight = getSetting("claude_model_light") || process.env.CLAUDE_MODEL_LIGHT || "claude-haiku-4-5-20251001";

  console.log(`[BUILD] Resuming build ${config.id} after conflict resolution`);

  const proc = spawn(pythonPath, [
    cliPath,
    "resolve",
    "--output", config.outputDir,
    "--resolutions", config.resolutionsPath,
    "--json-logs",
  ], {
    cwd: process.cwd(),
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1",
      PYTHONIOENCODING: "utf-8",
      CLAUDE_API_KEY: claudeApiKey,
      CLAUDE_MODEL: claudeModel,
      SEEKERS_CACHE_DIR: seekersCacheDir,
      CLAUDE_BASE_URL: claudeBaseUrl,
      CLAUDE_MODEL_LIGHT: claudeModelLight,
    },
  });

  runningProcesses.set(config.id, proc);

  let stdoutBuffer = "";
  proc.stdout.on("data", (chunk: Buffer) => {
    stdoutBuffer += chunk.toString();
    const lines = stdoutBuffer.split("\n");
    stdoutBuffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        handleParsedLog(config.id, JSON.parse(trimmed));
      } catch {
        handlePlainLog(config.id, trimmed);
      }
    }
  });

  let stderrBuffer = "";
  proc.stderr.on("data", (chunk: Buffer) => {
    stderrBuffer += chunk.toString();
    const lines = stderrBuffer.split("\n");
    stderrBuffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      if (trimmed.includes("DeprecationWarning") || trimmed.includes("FutureWarning")) {
        handlePlainLog(config.id, trimmed, "debug");
      } else {
        handlePlainLog(config.id, trimmed, "error");
      }
    }
  });

  proc.on("exit", (code, signal) => {
    runningProcesses.delete(config.id);
    if (stdoutBuffer.trim()) handlePlainLog(config.id, stdoutBuffer.trim());
    if (stderrBuffer.trim()) handlePlainLog(config.id, stderrBuffer.trim(), "error");

    const status = code === 0 ? "completed" : "failed";
    const now = new Date().toISOString();
    console.log(`[BUILD] Resolve ${config.id} exited: code=${code}, signal=${signal}`);

    updateBuild(config.id, {
      status,
      completed_at: now,
      error_message: code !== 0 ? `Resolve exited with code ${code}` : null,
    });

    insertBuildLog(config.id, {
      level: status === "completed" ? "info" : "error",
      message: `Build ${status} after conflict resolution`,
    });

    const build = getBuild(config.id);
    sseManager.broadcast(config.id, "complete", {
      status,
      quality_score: build?.quality_score,
      package_path: build?.package_path,
      completed_at: now,
    });

    if (build) notifyBuildComplete(build).catch(() => {});

    const processQueue = (globalThis as Record<string, unknown>).__processQueue as (() => void) | undefined;
    if (processQueue) processQueue();
  });

  proc.on("error", (err) => {
    runningProcesses.delete(config.id);
    console.error(`[BUILD] Resolve spawn error for ${config.id}:`, err.message);
    updateBuild(config.id, {
      status: "failed",
      completed_at: new Date().toISOString(),
      error_message: `Resolve spawn error: ${err.message}`,
    });
    insertBuildLog(config.id, { level: "error", message: `Failed to resume: ${err.message}` });
    sseManager.broadcast(config.id, "error", { message: err.message, retryable: true });
  });

  return proc;
}

// ─── Process Management ────────────────────────────────

export function stopBuild(buildId: string): boolean {
  const proc = runningProcesses.get(buildId);
  if (!proc) return false;

  console.log(`[BUILD] Stopping build ${buildId}`);
  proc.kill("SIGTERM");

  setTimeout(() => {
    if (runningProcesses.has(buildId)) {
      console.log(`[BUILD] Force killing build ${buildId}`);
      proc.kill("SIGKILL");
    }
  }, 5000);

  return true;
}

export function isBuildRunning(buildId: string): boolean {
  return runningProcesses.has(buildId);
}

export function getRunningCount(): number {
  return runningProcesses.size;
}

export function getRunningBuildIds(): string[] {
  return Array.from(runningProcesses.keys());
}
