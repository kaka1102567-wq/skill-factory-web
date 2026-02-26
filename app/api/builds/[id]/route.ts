import { NextResponse } from "next/server";
import { getBuild, getBuildLogs, deleteBuild } from "@/lib/db";
import { isBuildRunning } from "@/lib/build-runner";
import { isInsideBuildDir } from "@/lib/path-guard";
import fs from "fs";
import path from "path";

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build) {
    return NextResponse.json({ error: "Không tìm thấy build" }, { status: 404 });
  }

  const url = new URL(req.url);
  const content = url.searchParams.get("content");

  // Serve SKILL.md content
  if (content === "skill") {
    const outputDir = build.output_path || path.join(process.cwd(), "data", "builds", id, "output");
    if (!isInsideBuildDir(outputDir)) {
      return NextResponse.json({ error: "Đường dẫn build không hợp lệ" }, { status: 403 });
    }
    const candidates = [
      path.join(outputDir, "SKILL.md"),
      path.join(outputDir, "claude", "SKILL.md"),
    ];
    for (const p of candidates) {
      if (fs.existsSync(p)) {
        return NextResponse.json({ content: fs.readFileSync(p, "utf-8") });
      }
    }
    return NextResponse.json({ content: null }, { status: 404 });
  }

  // Serve knowledge files
  if (content === "knowledge") {
    const outputDir = build.output_path || path.join(process.cwd(), "data", "builds", id, "output");
    if (!isInsideBuildDir(outputDir)) {
      return NextResponse.json({ error: "Đường dẫn build không hợp lệ" }, { status: 403 });
    }
    const candidates = [
      path.join(outputDir, "knowledge"),
      path.join(outputDir, "claude", "knowledge"),
    ];
    for (const dir of candidates) {
      if (fs.existsSync(dir)) {
        const files = fs.readdirSync(dir)
          .filter((f: string) => f.endsWith(".md"))
          .map((f: string) => ({
            name: f,
            content: fs.readFileSync(path.join(dir, f), "utf-8"),
          }));
        return NextResponse.json({ files });
      }
    }
    return NextResponse.json({ files: [] });
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
    return NextResponse.json({ error: "Không tìm thấy build" }, { status: 404 });
  }

  if (isBuildRunning(id)) {
    return NextResponse.json(
      { error: "Không thể xoá build đang chạy. Hãy dừng build trước." },
      { status: 409 }
    );
  }

  const buildDir = path.join(process.cwd(), "data", "builds", id);
  if (fs.existsSync(buildDir)) {
    fs.rmSync(buildDir, { recursive: true, force: true });
  }

  deleteBuild(id);

  return NextResponse.json({ ok: true, message: "Đã xoá build" });
}
