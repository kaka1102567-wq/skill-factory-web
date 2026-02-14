import { NextResponse } from "next/server";
import { getAllSettings, setSetting } from "@/lib/db";

export async function GET() {
  const settings = getAllSettings();
  return NextResponse.json(settings);
}

export async function PUT(req: Request) {
  const body = await req.json();
  for (const [key, value] of Object.entries(body)) {
    if (typeof value === "string") {
      setSetting(key, value);
    }
  }
  return NextResponse.json({ ok: true });
}
