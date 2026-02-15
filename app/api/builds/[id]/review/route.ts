import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { getBuild, updateBuild, insertBuildLog, getSetting } from "@/lib/db";
import { sseManager } from "@/lib/sse-manager";
import { resumeAfterResolve } from "@/lib/build-runner";

const DATA_DIR = process.env.DATA_DIR || "./data";

interface ConflictAtom {
  title?: string;
  content?: string;
  source?: string;
  [key: string]: unknown;
}

interface RawConflict {
  id: string;
  atom_a: ConflictAtom;
  atom_b: ConflictAtom;
  conflict_type: string;
  description: string;
  baseline_evidence?: string;
  auto_resolved: boolean;
  resolution: string;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build)
    return NextResponse.json({ error: "Build not found" }, { status: 404 });

  // Read real conflicts.json from disk
  const conflictsPath = path.join(DATA_DIR, "builds", id, "output", "conflicts.json");
  let conflicts: Array<{
    id: string;
    atom_a: string;
    atom_b: string;
    source_a?: string;
    source_b?: string;
    baseline?: string;
    conflict_type?: string;
    description?: string;
  }> = [];

  if (fs.existsSync(conflictsPath)) {
    try {
      const raw = JSON.parse(fs.readFileSync(conflictsPath, "utf-8"));
      conflicts = (raw.conflicts || [])
        .filter((c: RawConflict) => !c.auto_resolved)
        .map((c: RawConflict) => ({
          id: c.id,
          atom_a: c.atom_a?.content || c.atom_a?.title || String(c.atom_a),
          atom_b: c.atom_b?.content || c.atom_b?.title || String(c.atom_b),
          source_a: c.atom_a?.source || "transcript",
          source_b: c.atom_b?.source || "baseline",
          baseline: c.baseline_evidence || undefined,
          conflict_type: c.conflict_type,
          description: c.description,
        }));
    } catch {
      // Malformed file — treat as no conflicts
    }
  }

  // Resolutions from DB
  const reviewData = build.review_data ? JSON.parse(build.review_data) : {};

  return NextResponse.json({
    buildId: id,
    status: build.review_status || (conflicts.length > 0 ? "pending" : "resolved"),
    conflicts,
    resolutions: reviewData.resolutions || {},
    conflict_summary: reviewData.conflict_summary || null,
  });
}

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build)
    return NextResponse.json({ error: "Build not found" }, { status: 404 });

  const { resolutions } = await req.json();

  // 1. Save resolutions to DB
  updateBuild(id, {
    review_status: "resolved",
    review_data: JSON.stringify({ resolutions }),
  });

  insertBuildLog(id, {
    level: "info",
    message: `Conflict review completed: ${Object.keys(resolutions).length} resolved`,
  });

  // 2. Write resolutions.json to disk
  const buildDir = path.join(DATA_DIR, "builds", id);
  const outputDir = path.join(buildDir, "output");
  const resolutionsPath = path.join(outputDir, "resolutions.json");
  fs.writeFileSync(resolutionsPath, JSON.stringify(resolutions, null, 2), "utf-8");

  // 3. Resume build: spawn cli.py resolve
  updateBuild(id, { status: "running" });

  sseManager.broadcast(id, "log", {
    level: "info",
    message: "Build resumed after conflict review",
    timestamp: new Date().toISOString(),
  });

  resumeAfterResolve({
    id,
    name: build.name,
    outputDir,
    resolutionsPath: resolutionsPath,
  });

  return NextResponse.json({
    ok: true,
    resolved: Object.keys(resolutions).length,
  });
}
