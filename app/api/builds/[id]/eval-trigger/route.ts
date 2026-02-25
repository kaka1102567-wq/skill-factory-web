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

  const outputDir =
    build.output_path ||
    path.join(process.cwd(), "data", "builds", id, "output");

  const reportPath = path.join(outputDir, "p6_optimization_report.json");

  if (!fs.existsSync(reportPath)) {
    return NextResponse.json({ eval_set: [], report: null });
  }

  try {
    const raw = fs.readFileSync(reportPath, "utf-8");
    const report = JSON.parse(raw);
    const eval_set = report.eval_set || [];
    return NextResponse.json({ eval_set, report });
  } catch {
    return NextResponse.json({ eval_set: [], report: null });
  }
}
