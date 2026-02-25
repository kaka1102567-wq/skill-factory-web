import { NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
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

  const { searchParams } = new URL(req.url);
  const file = searchParams.get("file");

  if (!file) {
    return NextResponse.json({ error: "?file= parameter required" }, { status: 400 });
  }

  // Sanitize: basename only, must end with .json
  const safeName = path.basename(file);
  if (!safeName.endsWith(".json")) {
    return NextResponse.json({ error: "Only .json files allowed" }, { status: 400 });
  }

  const outputDir =
    build.output_path ||
    path.join(process.cwd(), "data", "builds", id, "output");

  const filePath = path.join(outputDir, safeName);

  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ error: "Report file not found" }, { status: 404 });
  }

  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    const parsed = JSON.parse(raw);
    return NextResponse.json(parsed);
  } catch {
    return NextResponse.json({ error: "Failed to parse report file" }, { status: 500 });
  }
}
