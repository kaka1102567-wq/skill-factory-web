import { getDb } from "./db";

export function submitFeedback(
  buildId: string,
  domain: string,
  rating: number,
  feedback: string,
  issues: string[]
) {
  const db = getDb();
  db.prepare(
    `INSERT INTO build_feedback (build_id, domain, rating, feedback, issues)
     VALUES (?, ?, ?, ?, ?)`
  ).run(buildId, domain, rating, feedback, JSON.stringify(issues));
}

export function getDomainLessons(domain: string, limit: number = 5): string {
  const db = getDb();
  const rows = db.prepare(`
    SELECT rating, feedback, issues FROM build_feedback
    WHERE domain = ? AND feedback IS NOT NULL AND feedback != ''
    ORDER BY created_at DESC LIMIT ?
  `).all(domain, limit) as { rating: number; feedback: string; issues: string }[];

  if (!rows.length) return "";

  const avgRating = rows.reduce((sum, r) => sum + r.rating, 0) / rows.length;
  const lines = rows.map((r, i) => {
    let issues = "none";
    try { issues = r.issues ? JSON.parse(r.issues).join(", ") : "none"; } catch { /* malformed */ }
    return `${i + 1}. Rating: ${r.rating}/5 | Issues: ${issues}\n   ${r.feedback}`;
  });

  return `LESSONS FROM PREVIOUS BUILDS (domain: ${domain}, avg rating: ${avgRating.toFixed(1)}/5):\n${lines.join("\n")}`;
}
