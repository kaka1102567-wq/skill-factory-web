import { NextResponse } from "next/server";
import { getBuild, updateBuild, insertBuildLog } from "@/lib/db";
import { stopBuild, isBuildRunning } from "@/lib/build-runner";
import { sseManager } from "@/lib/sse-manager";
import { removeFromQueue } from "@/lib/build-queue";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build) {
    return NextResponse.json({ error: "Build not found" }, { status: 404 });
  }

  if (isBuildRunning(id)) {
    stopBuild(id);
    updateBuild(id, { status: "failed", completed_at: new Date().toISOString(), error_message: "Stopped by user" });
    insertBuildLog(id, { level: "warn", message: "Build stopped by user" });
    sseManager.broadcast(id, "complete", { status: "failed", reason: "stopped_by_user" });
    return NextResponse.json({ stopped: true, was: "running" });
  }

  if (removeFromQueue(id)) {
    updateBuild(id, { status: "failed", error_message: "Removed from queue by user" });
    return NextResponse.json({ stopped: true, was: "queued" });
  }

  return NextResponse.json(
    { stopped: false, message: "Build is not running or queued" },
    { status: 409 }
  );
}
