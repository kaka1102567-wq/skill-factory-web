import { NextResponse } from "next/server";
import { getDashboardStats } from "@/lib/db";
import { getRunningCount, getRunningBuildIds } from "@/lib/build-runner";
import { getQueueLength } from "@/lib/build-queue";

export async function GET() {
  const stats = getDashboardStats();

  return NextResponse.json({
    ...stats,
    active_running: getRunningCount(),
    queue_length: getQueueLength(),
    running_build_ids: getRunningBuildIds(),
  });
}
