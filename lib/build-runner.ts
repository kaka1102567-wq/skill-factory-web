import { spawn, ChildProcess } from "child_process";
import path from "path";
import { updateBuild, insertBuildLog, getBuild, getSetting } from "./db";
import { sseManager } from "./sse-manager";
import { notifyBuildComplete } from "./notifications";
import type { PhaseId } from "@/types/build";

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

  // Read API keys and pipeline settings from Settings DB
  const claudeApiKey = getSetting("claude_api_key") || process.env.CLAUDE_API_KEY || "";
  const claudeModel = getSetting("claude_model") || process.env.CLAUDE_MODEL || "claude-sonnet-4-20250514";
  const seekersCacheDir = getSetting("seekers_cache_dir") || process.env.SEEKERS_CACHE_DIR || "./data/cache";

  const proc = spawn(pythonPath, [
    cliPath,
    "build",
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
    },
  });

  runningProcesses.set(config.id, proc);

  // ─── STDOUT: Parse JSON log lines ─────────────────
  let stdoutBuffer = "";

  proc.stdout.on("data", (chunk: Buffer) => {
    stdoutBuffer += chunk.toString();
    const lines = stdoutBuffer.split("\n");
    stdoutBuffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      try {
        const parsed = JSON.parse(trimmed);
        handleParsedLog(config.id, parsed);
      } catch {
        handlePlainLog(config.id, trimmed);
      }
    }
  });

  // ─── STDERR: Capture errors ───────────────────────
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

  // ─── EXIT: Process completed ──────────────────────
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

    // Send Telegram notification
    if (build) {
      notifyBuildComplete(build).catch(() => {});
    }

    // Process queue: start next pending build
    const processQueue = (globalThis as Record<string, unknown>).__processQueue as (() => void) | undefined;
    if (processQueue) {
      processQueue();
    }
  });

  // ─── ERROR: Spawn failure ────────────────────────
  proc.on("error", (err) => {
    runningProcesses.delete(config.id);
    console.error(`[BUILD] Spawn error for ${config.id}:`, err.message);

    updateBuild(config.id, {
      status: "failed",
      completed_at: new Date().toISOString(),
      error_message: `Spawn error: ${err.message}`,
    });

    insertBuildLog(config.id, {
      level: "error",
      message: `Failed to start build: ${err.message}`,
    });

    sseManager.broadcast(config.id, "error", {
      message: err.message,
      retryable: true,
    });
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
  }

  if (event === "conflict") {
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
