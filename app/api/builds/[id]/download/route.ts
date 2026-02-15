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

  if (build.status !== "completed") {
    return NextResponse.json({ error: "Build not completed yet" }, { status: 400 });
  }

  // Try package_path first (resolve relative paths), then scan output dir
  const dataDir = process.env.DATA_DIR || "./data";
  let zipPath = build.package_path
    ? path.resolve(process.cwd(), build.package_path)
    : null;
  if (!zipPath || !fs.existsSync(zipPath)) {
    // Direct path: data/builds/<id>/output/package.zip
    const directPath = path.join(process.cwd(), dataDir, "builds", id, "output", "package.zip");
    if (fs.existsSync(directPath)) {
      zipPath = directPath;
    }
  }
  if (!zipPath || !fs.existsSync(zipPath)) {
    const outputDir = path.join(process.cwd(), dataDir, "builds", id, "output");
    if (fs.existsSync(outputDir)) {
      const files = fs.readdirSync(outputDir);
      const zipFile = files.find(f => f.endsWith(".zip"));
      if (zipFile) {
        zipPath = path.join(outputDir, zipFile);
      }
    }
  }

  if (!zipPath || !fs.existsSync(zipPath)) {
    return NextResponse.json({ error: "Package .zip not found" }, { status: 404 });
  }

  const fileBuffer = fs.readFileSync(zipPath);
  const fileName = `${build.name.replace(/[^a-zA-Z0-9-_]/g, "_")}_skill.zip`;

  return new Response(fileBuffer, {
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": `attachment; filename="${fileName}"`,
      "Content-Length": fileBuffer.length.toString(),
    },
  });
}
