"use client";

import { useState } from "react";
import { CheckCircle, XCircle, AlertCircle, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface FactResult {
  fact: string;
  present: boolean;
  evidence?: string;
}

export interface SmokeTest {
  prompt: string;
  passed: boolean;
  score?: number;
  grade_notes?: string;
  response?: string;
  response_preview?: string;
  expected_facts?: string[];
  grade_results?: FactResult[];
  category?: string;
  complexity?: string;
}

export interface SmokeReport {
  results?: SmokeTest[];
  pass_count?: number;
  total?: number;
  score?: number;
  passed?: boolean;
}

/** Determine color tier: pass (green), warn (amber), fail (red) */
function getTier(t: SmokeTest) {
  if (t.passed) return "pass" as const;
  const score = t.score ?? 0;
  return score >= 0.4 ? "warn" as const : "fail" as const;
}

const TIER_CONFIG = {
  pass: { Icon: CheckCircle, iconColor: "text-emerald-400", border: "border-emerald-500/20", badge: "bg-emerald-500/10 text-emerald-400" },
  warn: { Icon: AlertCircle, iconColor: "text-amber-400", border: "border-amber-500/20", badge: "bg-amber-500/10 text-amber-400" },
  fail: { Icon: XCircle, iconColor: "text-red-400", border: "border-red-500/20", badge: "bg-red-500/10 text-red-400" },
};

/** Expandable smoke test results with 3-tier coloring and per-fact grading */
export function SmokeTestDetail({ report }: { report: SmokeReport }) {
  const [expandedTest, setExpandedTest] = useState<number | null>(null);
  const passCount = report.pass_count ?? 0;
  const total = report.total ?? 0;
  const failCount = total - passCount;
  const passRatio = total > 0 ? passCount / total : 0;
  const summaryColor = passRatio >= 0.6 ? "text-emerald-400" : passCount > 0 ? "text-amber-400" : "text-red-400";

  return (
    <div className="p-4 rounded-xl bg-card border border-border">
      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
        Smoke Tests (
        <span className={summaryColor}>{passCount} passed</span>
        {failCount > 0 && (
          <span className={summaryColor}> · {failCount} {passRatio >= 0.6 ? "failed" : "warnings"}</span>
        )}
        )
        <span className="ml-2 normal-case font-normal">— Click để xem chi tiết</span>
      </h4>

      <div className="space-y-2">
        {(report.results ?? []).map((t, i) => {
          const tier = getTier(t);
          const { Icon: TierIcon, iconColor, border, badge } = TIER_CONFIG[tier];
          const score = t.score ?? (t.passed ? 1 : 0);
          const isExpanded = expandedTest === i;

          return (
            <div key={i} className={cn("rounded-lg border transition-colors", border, isExpanded ? "bg-muted/30" : "bg-transparent hover:bg-muted/20")}>
              {/* Collapsed row */}
              <div className="flex items-center gap-2 p-3 cursor-pointer" onClick={() => setExpandedTest(isExpanded ? null : i)}>
                <TierIcon className={cn("w-4 h-4 shrink-0", iconColor)} />
                <span className="text-sm text-foreground flex-1 line-clamp-1">{t.prompt}</span>
                <span className={cn("text-xs font-mono px-1.5 py-0.5 rounded shrink-0", badge)}>
                  {Math.round(score * 100)}%
                </span>
                {t.complexity && <span className="text-xs text-muted-foreground shrink-0">{t.complexity}</span>}
                <ChevronDown className={cn("w-4 h-4 text-muted-foreground transition-transform shrink-0", isExpanded && "rotate-180")} />
              </div>

              {/* Expanded detail */}
              {isExpanded && (
                <div className="px-3 pb-3 space-y-3 border-t border-border/50">
                  {/* Question */}
                  <div className="pt-3">
                    <SectionLabel>Câu hỏi test</SectionLabel>
                    <p className="text-sm text-foreground">{t.prompt}</p>
                  </div>

                  {/* Per-fact grading */}
                  {t.expected_facts && t.expected_facts.length > 0 && (
                    <div>
                      <SectionLabel>
                        Kiến thức cần có ({t.grade_results
                          ? `${t.grade_results.filter(r => r.present).length}/${t.expected_facts.length}`
                          : `${t.expected_facts.length} facts`})
                      </SectionLabel>
                      <div className="space-y-1">
                        {t.expected_facts.map((fact, fi) => {
                          const gr = t.grade_results?.[fi];
                          const present = gr?.present ?? false;
                          return (
                            <div key={fi} className="flex items-start gap-2 text-xs">
                              {gr ? (
                                present
                                  ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                                  : <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                              ) : (
                                <span className="w-3.5 h-3.5 shrink-0" />
                              )}
                              <div className="flex-1">
                                <span className={present ? "text-foreground" : "text-muted-foreground"}>{fact}</span>
                                {gr?.evidence && present && (
                                  <p className="text-muted-foreground mt-0.5 italic">&quot;{gr.evidence}&quot;</p>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Agent response */}
                  <div>
                    <SectionLabel>Câu trả lời của Agent</SectionLabel>
                    <div className="max-h-64 overflow-y-auto rounded-lg bg-muted/40 p-3">
                      <pre className="text-xs text-foreground whitespace-pre-wrap font-sans">
                        {t.response || t.response_preview || "(Không có dữ liệu — build cũ chỉ lưu 300 ký tự đầu)"}
                      </pre>
                    </div>
                  </div>

                  {/* Grading notes */}
                  {t.grade_notes && (
                    <div>
                      <SectionLabel>Nhận xét chấm điểm</SectionLabel>
                      <p className={cn("text-xs", TIER_CONFIG[tier].iconColor)}>{t.grade_notes}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-xs font-semibold text-muted-foreground uppercase mb-1">{children}</p>;
}
