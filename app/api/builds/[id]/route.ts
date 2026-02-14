import { NextResponse } from "next/server";
import { getBuild, getBuildLogs, deleteBuild } from "@/lib/db";
import { isBuildRunning } from "@/lib/build-runner";
import fs from "fs";
import path from "path";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build) {
    return NextResponse.json({ error: "Build not found" }, { status: 404 });
  }

  const logs = getBuildLogs(id, 100);

  return NextResponse.json({
    ...build,
    logs,
    is_running: isBuildRunning(id),
  });
}

export async function DELETE(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build) {
    return NextResponse.json({ error: "Build not found" }, { status: 404 });
  }

  if (isBuildRunning(id)) {
    return NextResponse.json(
      { error: "Cannot delete a running build. Stop it first." },
      { status: 409 }
    );
  }

  const buildDir = path.join(process.cwd(), "data", "builds", id);
  if (fs.existsSync(buildDir)) {
    fs.rmSync(buildDir, { recursive: true, force: true });
  }

  deleteBuild(id);

  return NextResponse.json({ ok: true, message: "Build deleted" });
}
