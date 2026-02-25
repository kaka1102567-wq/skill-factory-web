import { NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
import fs from "fs";
import path from "path";

function readReport(outputDir: string): Record<string, unknown> | null {
  const reportPath = path.join(outputDir, "p6_optimization_report.json");
  if (!fs.existsSync(reportPath)) return null;
  try {
    return JSON.parse(fs.readFileSync(reportPath, "utf-8"));
  } catch {
    return null;
  }
}

function readDescription(outputDir: string, report: Record<string, unknown> | null): string {
  // CRITICAL PATCH P10: read from p6_optimization_report.json first
  // yaml.dump produces multi-line folded block scalars that regex would truncate
  if (report && typeof report.best_description === "string") {
    return report.best_description;
  }
  // Fallback: read SKILL.md and extract description field raw value
  const skillPath = path.join(outputDir, "SKILL.md");
  if (!fs.existsSync(skillPath)) return "";
  try {
    const content = fs.readFileSync(skillPath, "utf-8");
    // Extract the raw description block from frontmatter (may be multi-line)
    const fmMatch = content.match(/^---\s*\n([\s\S]*?)\n---/);
    if (!fmMatch) return "";
    const fm = fmMatch[1];
    // Find description key and capture value (handles folded ">" and literal "|" blocks)
    const descMatch = fm.match(/^description:\s*([\s\S]*?)(?=\n\w|\n---$|$)/m);
    if (!descMatch) return "";
    return descMatch[1].replace(/^[>|]\s*/, "").replace(/\n\s+/g, " ").trim();
  } catch {
    return "";
  }
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const aId = searchParams.get("a");
  const bId = searchParams.get("b");

  if (!aId || !bId) {
    return NextResponse.json(
      { error: "Both ?a= and ?b= build IDs are required" },
      { status: 400 }
    );
  }

  const buildA = getBuild(aId);
  const buildB = getBuild(bId);

  if (!buildA) {
    return NextResponse.json({ error: `Build not found: ${aId}` }, { status: 404 });
  }
  if (!buildB) {
    return NextResponse.json({ error: `Build not found: ${bId}` }, { status: 404 });
  }

  const dirA = buildA.output_path || path.join(process.cwd(), "data", "builds", aId, "output");
  const dirB = buildB.output_path || path.join(process.cwd(), "data", "builds", bId, "output");

  const reportA = readReport(dirA);
  const reportB = readReport(dirB);

  const descriptionA = readDescription(dirA, reportA);
  const descriptionB = readDescription(dirB, reportB);

  return NextResponse.json({
    a: { ...buildA, description: descriptionA, p6_report: reportA },
    b: { ...buildB, description: descriptionB, p6_report: reportB },
  });
}
