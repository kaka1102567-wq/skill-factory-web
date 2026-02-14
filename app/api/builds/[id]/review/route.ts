import { NextResponse } from "next/server";
import { getBuild, updateBuild, insertBuildLog } from "@/lib/db";
import { sseManager } from "@/lib/sse-manager";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build)
    return NextResponse.json({ error: "Build not found" }, { status: 404 });

  return NextResponse.json({
    review_status: build.review_status,
    review_data: build.review_data ? JSON.parse(build.review_data) : null,
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

  // Store resolutions and mark review completed
  updateBuild(id, {
    review_status: "completed",
    review_data: JSON.stringify({ resolutions }),
  });

  insertBuildLog(id, {
    level: "info",
    message: `Conflict review completed: ${Object.keys(resolutions).length} resolved`,
  });

  // Resume build
  updateBuild(id, { status: "running" });
  sseManager.broadcast(id, "log", {
    level: "info",
    message: "Build resumed after conflict review",
    timestamp: new Date().toISOString(),
  });

  return NextResponse.json({
    ok: true,
    resolved: Object.keys(resolutions).length,
  });
}
