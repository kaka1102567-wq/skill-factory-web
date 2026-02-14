import { getDb, getSetting } from "./db";
import fs from "fs";
import path from "path";

export function cleanupOldBuilds(): { deleted: number; freedMB: number } {
  const days = parseInt(getSetting("auto_cleanup_days") || "30", 10);
  if (days <= 0) return { deleted: 0, freedMB: 0 };

  const db = getDb();
  const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const oldBuilds = db.prepare(`
    SELECT id FROM builds
    WHERE status IN ('completed', 'failed')
    AND created_at < ?
  `).all(cutoff) as { id: string }[];

  let totalFreed = 0;

  for (const { id } of oldBuilds) {
    const buildDir = path.join(process.cwd(), "data", "builds", id);
    if (fs.existsSync(buildDir)) {
      const size = getDirSize(buildDir);
      totalFreed += size;
      fs.rmSync(buildDir, { recursive: true, force: true });
    }

    db.prepare("DELETE FROM build_logs WHERE build_id = ?").run(id);
    db.prepare("DELETE FROM builds WHERE id = ?").run(id);
  }

  console.log(`[CLEANUP] Deleted ${oldBuilds.length} builds, freed ${(totalFreed / 1024 / 1024).toFixed(1)}MB`);
  return { deleted: oldBuilds.length, freedMB: Math.round(totalFreed / 1024 / 1024) };
}

function getDirSize(dirPath: string): number {
  let total = 0;
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name);
      if (entry.isDirectory()) {
        total += getDirSize(fullPath);
      } else {
        total += fs.statSync(fullPath).size;
      }
    }
  } catch {
    // Ignore permission errors
  }
  return total;
}

export function cleanupOrphanedUploads(): number {
  const uploadsDir = path.join(process.cwd(), "data", "uploads");
  if (!fs.existsSync(uploadsDir)) return 0;

  const cutoff = Date.now() - 24 * 60 * 60 * 1000;
  let cleaned = 0;

  const entries = fs.readdirSync(uploadsDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const dirPath = path.join(uploadsDir, entry.name);
    const stat = fs.statSync(dirPath);
    if (stat.mtimeMs < cutoff) {
      fs.rmSync(dirPath, { recursive: true, force: true });
      cleaned++;
    }
  }

  return cleaned;
}
