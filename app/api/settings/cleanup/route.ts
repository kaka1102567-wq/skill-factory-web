import { NextResponse } from "next/server";
import { cleanupOldBuilds, cleanupOrphanedUploads } from "@/lib/cleanup";

export async function POST() {
  const result = cleanupOldBuilds();
  const orphaned = cleanupOrphanedUploads();
  return NextResponse.json({ ...result, orphaned_uploads_cleaned: orphaned });
}
