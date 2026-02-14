import { v4 as uuidv4 } from "uuid";
import path from "path";
import fs from "fs";
import { createBuild, updateBuild, getSetting, incrementTemplateUsage } from "./db";
import { startBuild, getRunningCount, type BuildConfig } from "./build-runner";

export interface BuildRequest {
  name: string;
  domain: string | null;
  config_yaml: string;
  template_id: string | null;
  created_by: string;
  files?: string[];
}

interface QueueEntry {
  buildId: string;
  config: BuildConfig;
  request: BuildRequest;
}

// Global queue state (survives hot reload)
const globalForQueue = globalThis as unknown as { pendingQueue: QueueEntry[] };
if (!globalForQueue.pendingQueue) {
  globalForQueue.pendingQueue = [];
}
const pendingQueue = globalForQueue.pendingQueue;

export function enqueueBuild(request: BuildRequest): { buildId: string; position: number } {
  const buildId = uuidv4();
  const maxConcurrent = parseInt(getSetting("max_concurrent_builds") || "2", 10);
  const dataDir = process.env.DATA_DIR || "./data";

  const buildDir = path.join(dataDir, "builds", buildId);
  const outputDir = path.join(buildDir, "output");
  const configPath = path.join(buildDir, "config.yaml");

  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(configPath, request.config_yaml, "utf-8");

  if (request.files && request.files.length > 0) {
    const inputDir = path.join(buildDir, "input");
    fs.mkdirSync(inputDir, { recursive: true });
    for (const filePath of request.files) {
      const destPath = path.join(inputDir, path.basename(filePath));
      fs.copyFileSync(filePath, destPath);
    }
  }

  createBuild({
    id: buildId,
    name: request.name,
    domain: request.domain,
    config_yaml: request.config_yaml,
    template_id: request.template_id,
    created_by: request.created_by,
  });

  if (request.template_id) {
    incrementTemplateUsage(request.template_id);
  }

  const buildConfig: BuildConfig = {
    id: buildId,
    name: request.name,
    configPath,
    outputDir,
  };

  if (getRunningCount() < maxConcurrent) {
    startBuild(buildConfig);
    return { buildId, position: 0 };
  } else {
    updateBuild(buildId, { status: "queued" as const });
    pendingQueue.push({ buildId, config: buildConfig, request });
    return { buildId, position: pendingQueue.length };
  }
}

export function processQueue(): void {
  const maxConcurrent = parseInt(getSetting("max_concurrent_builds") || "2", 10);

  while (getRunningCount() < maxConcurrent && pendingQueue.length > 0) {
    const next = pendingQueue.shift()!;
    console.log(`[QUEUE] Dequeuing build ${next.buildId}. Remaining: ${pendingQueue.length}`);
    startBuild(next.config);
  }
}

export function getQueuePosition(buildId: string): number {
  const idx = pendingQueue.findIndex((e) => e.buildId === buildId);
  return idx + 1;
}

export function removeFromQueue(buildId: string): boolean {
  const idx = pendingQueue.findIndex((e) => e.buildId === buildId);
  if (idx >= 0) {
    pendingQueue.splice(idx, 1);
    return true;
  }
  return false;
}

export function getQueueLength(): number {
  return pendingQueue.length;
}

// Register processQueue callback for build-runner to call on exit
// Avoids circular imports: build-queue → build-runner → (on exit) → build-queue.processQueue
if (typeof globalThis !== "undefined") {
  (globalThis as Record<string, unknown>).__processQueue = processQueue;
}
