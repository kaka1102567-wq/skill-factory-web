import { NextResponse } from "next/server";
import { getBuild } from "@/lib/db";
import { submitFeedback } from "@/lib/feedback";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const build = getBuild(id);
  if (!build) {
    return NextResponse.json({ error: "Không tìm thấy build" }, { status: 404 });
  }

  let body: { rating: number; feedback?: string; issues?: string[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "JSON body không hợp lệ" }, { status: 400 });
  }

  const { rating, feedback = "", issues = [] } = body;

  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    return NextResponse.json(
      { error: "rating phải là số nguyên từ 1 đến 5" },
      { status: 422 }
    );
  }

  // Input length validation to prevent abuse
  const safeFeedback = typeof feedback === "string" ? feedback.slice(0, 2000) : "";
  const safeIssues = Array.isArray(issues) ? issues.slice(0, 10).map(i => String(i).slice(0, 100)) : [];

  submitFeedback(id, build.domain || "", rating, safeFeedback, safeIssues);

  return NextResponse.json({ ok: true });
}
