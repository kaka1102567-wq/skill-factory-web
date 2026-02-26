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
    return NextResponse.json({ error: "Không tìm thấy build" }, { status: 404 });
  }

  if (isBuildRunning(id)) {
    stopBuild(id);
    updateBuild(id, { status: "failed", completed_at: new Date().toISOString(), error_message: "Người dùng dừng build" });
    insertBuildLog(id, { level: "warn", message: "Build bị dừng bởi người dùng" });
    sseManager.broadcast(id, "complete", { status: "failed", reason: "stopped_by_user" });
    return NextResponse.json({ stopped: true, was: "running" });
  }

  if (removeFromQueue(id)) {
    updateBuild(id, { status: "failed", error_message: "Người dùng xoá khỏi hàng đợi" });
    return NextResponse.json({ stopped: true, was: "queued" });
  }

  return NextResponse.json(
    { stopped: false, message: "Build không đang chạy hoặc xếp hàng" },
    { status: 409 }
  );
}
