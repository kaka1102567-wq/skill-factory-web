import { NextResponse } from "next/server";
import { getBaselineForDomain } from "@/lib/baseline-registry";
import fs from "fs";
import path from "path";

interface RefDetail {
  filename: string;
  title: string;
  source_url: string;
  size_bytes: number;
  content: string;
}

interface BaselineDetail {
  domain: string;
  name: string;
  status: string;
  score: number;
  source: string;
  skill_md: string;
  topics: string[];
  references: RefDetail[];
  total_tokens: number;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ domain: string }> },
) {
  const { domain } = await params;
  const info = getBaselineForDomain(domain);

  if (info.status !== "ready" || !info.path) {
    return NextResponse.json({ error: "Baseline not found or not ready" }, { status: 404 });
  }

  // Read baseline_summary.json from the baseline output directory
  const summaryPath = path.join(info.path, "baseline_summary.json");
  if (!fs.existsSync(summaryPath)) {
    return NextResponse.json({ error: "baseline_summary.json not found" }, { status: 404 });
  }

  const summary = JSON.parse(fs.readFileSync(summaryPath, "utf-8"));

  // Parse references with metadata extracted from content
  const references: RefDetail[] = (summary.references || []).map((ref: { path: string; content?: string }) => {
    const filename = path.basename(ref.path);
    const content = ref.content || "";

    // Extract title from first markdown heading
    const titleMatch = content.match(/^#\s+(.+)$/m);
    const title = titleMatch ? titleMatch[1] : filename.replace(/-/g, " ").replace(/\.md$/, "");

    // Extract source URL from "Source: https://..." line
    const sourceMatch = content.match(/Source:\s*(https?:\/\/\S+)/i);
    const source_url = sourceMatch ? sourceMatch[1] : "";

    // Calculate file size from content
    const refFilePath = path.join(info.path, ref.path);
    let size_bytes: number;
    try {
      size_bytes = fs.existsSync(refFilePath)
        ? fs.statSync(refFilePath).size
        : Buffer.byteLength(content, "utf-8");
    } catch {
      size_bytes = Buffer.byteLength(content, "utf-8");
    }

    return { filename, title, source_url, size_bytes, content };
  });

  const detail: BaselineDetail = {
    domain,
    name: info.name || domain,
    status: "ready",
    score: summary.score || 0,
    source: summary.source || "unknown",
    skill_md: summary.skill_md || "",
    topics: summary.topics || [],
    references,
    total_tokens: summary.total_tokens || 0,
  };

  return NextResponse.json(detail);
}
