import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import type { Template } from "@/types/build";

export async function GET() {
  const db = getDb();
  const templates = db.prepare(
    "SELECT * FROM templates ORDER BY is_default DESC, usage_count DESC"
  ).all() as Template[];
  return NextResponse.json(templates);
}
