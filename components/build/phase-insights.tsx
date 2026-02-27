"use client";

import { useState, useEffect } from "react";
import { ChevronDown, CheckCircle2, AlertTriangle, AlertOctagon, Info, Lightbulb } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";
import type { PhaseState } from "@/hooks/use-build-stream";
import { analyzePhase, type PhaseAnalysis, type PhaseInsight } from "@/lib/phase-insights-engine";

interface PhaseInsightsProps {
  buildId: string;
  phases: PhaseState[];
  buildStatus: string;
}

const PHASE_LABELS: Record<string, string> = {
  p0: "Baseline",
  p1: "Audit",
  p2: "Extract",
  p3: "Deduplicate",
  p4: "Verify",
  p5: "Architect",
};

const ANALYSIS_PHASES = ["p0", "p1", "p2", "p3", "p4", "p5"];

function scoreBadgeClass(score: number): string {
  if (score >= 90) return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
  if (score >= 80) return "bg-blue-500/15 text-blue-400 border-blue-500/30";
  if (score >= 70) return "bg-amber-500/15 text-amber-400 border-amber-500/30";
  return "bg-red-500/15 text-red-400 border-red-500/30";
}

function InsightIcon({ type }: { type: PhaseInsight["type"] }) {
  const base = "w-3.5 h-3.5 shrink-0 mt-0.5";
  switch (type) {
    case "good":
      return <CheckCircle2 className={cn(base, "text-emerald-400")} />;
    case "warning":
      return <AlertTriangle className={cn(base, "text-amber-400")} />;
    case "critical":
      return <AlertOctagon className={cn(base, "text-red-400")} />;
    case "tip":
      return <Lightbulb className={cn(base, "text-purple-400")} />;
    case "info":
    default:
      return <Info className={cn(base, "text-blue-400")} />;
  }
}

function insightTextClass(type: PhaseInsight["type"]): string {
  switch (type) {
    case "good":
      return "text-emerald-300";
    case "warning":
      return "text-amber-300";
    case "critical":
      return "text-red-300";
    case "tip":
      return "text-purple-300";
    case "info":
    default:
      return "text-blue-300";
  }
}

function priorityBadgeClass(priority: "high" | "medium" | "low"): string {
  switch (priority) {
    case "high":
      return "bg-red-500/10 text-red-400 border-red-500/20";
    case "medium":
      return "bg-amber-500/10 text-amber-400 border-amber-500/20";
    case "low":
    default:
      return "bg-blue-500/10 text-blue-400 border-blue-500/20";
  }
}

const COVERAGE_COLORS = {
  overlap: "#3b82f6",
  unique: "#10b981",
  gap: "#ef4444",
};

export function PhaseInsights({ buildId, phases, buildStatus }: PhaseInsightsProps) {
  const [phaseAnalyses, setPhaseAnalyses] = useState<Record<string, PhaseAnalysis>>({});
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (buildStatus !== "completed" && buildStatus !== "failed") return;
    fetch(`/api/builds/${buildId}/reports?file=state.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.phase_results) {
          const analyses: Record<string, PhaseAnalysis> = {};
          for (const [id, result] of Object.entries(data.phase_results)) {
            analyses[id] = analyzePhase(id, result as any);
          }
          setPhaseAnalyses(analyses);
        }
      })
      .catch(() => {});
  }, [buildId, buildStatus]);

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const visiblePhases = phases.filter((p) => ANALYSIS_PHASES.includes(p.id));

  return (
    <div className="space-y-2">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-foreground">Phân Tích Chi Tiết</h3>
        <p className="text-xs text-muted-foreground mt-0.5">Insights từng phase của pipeline</p>
      </div>

      {visiblePhases.map((phase) => {
        const analysis = phaseAnalyses[phase.id];
        const isOpen = expanded.has(phase.id);
        const score = phase.score ?? 0;
        const label = PHASE_LABELS[phase.id] ?? phase.name;

        return (
          <div key={phase.id} className="rounded-xl bg-card border border-border overflow-hidden">
            {/* Header */}
            <button
              onClick={() => toggleExpand(phase.id)}
              className="w-full flex items-center gap-3 p-3 text-left hover:bg-muted/40 transition-all duration-200"
            >
              <span
                className={cn(
                  "text-xs font-bold px-2 py-0.5 rounded-md border shrink-0",
                  phase.score !== null ? scoreBadgeClass(score) : "bg-muted text-muted-foreground border-border"
                )}
              >
                {phase.score !== null ? Math.round(score) : "—"}
              </span>
              <div className="flex-1 min-w-0">
                <span className="text-xs font-semibold text-foreground">{label}</span>
                {analysis ? (
                  <p className="text-xs text-muted-foreground truncate">{analysis.summary}</p>
                ) : (
                  <p className="text-xs text-muted-foreground capitalize">{phase.status}</p>
                )}
              </div>
              <ChevronDown
                className={cn(
                  "w-4 h-4 text-muted-foreground shrink-0 transition-transform duration-200",
                  isOpen && "rotate-180"
                )}
              />
            </button>

            {/* Expanded content */}
            {isOpen && analysis && (
              <div className="px-3 pb-3 space-y-3 border-t border-border pt-3">
                {/* Metrics row */}
                {analysis.metrics.length > 0 && (
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                    {analysis.metrics.map((m, i) => (
                      <div key={i} className="bg-muted rounded-lg px-2.5 py-1.5">
                        <p className="text-[10px] text-muted-foreground">{m.label}</p>
                        <p className="text-xs font-semibold text-foreground">
                          {m.value}
                          {m.unit && <span className="text-muted-foreground ml-0.5">{m.unit}</span>}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Score breakdown — P1 only */}
                {analysis.breakdown.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                      Score Breakdown
                    </p>
                    {analysis.breakdown.map((comp, i) => (
                      <div key={i}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-foreground">{comp.name}</span>
                          <span className="text-xs text-muted-foreground">{comp.detail}</span>
                          <span
                            className={cn(
                              "text-xs font-bold",
                              comp.status === "good"
                                ? "text-emerald-400"
                                : comp.status === "warning"
                                  ? "text-amber-400"
                                  : "text-red-400"
                            )}
                          >
                            {Math.round(comp.score)}
                          </span>
                        </div>
                        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all duration-200",
                              comp.status === "good"
                                ? "bg-emerald-400"
                                : comp.status === "warning"
                                  ? "bg-amber-400"
                                  : "bg-red-400"
                            )}
                            style={{ width: `${Math.min(100, Math.max(0, comp.score))}%` }}
                          />
                        </div>
                        <p className="text-[10px] text-muted-foreground mt-0.5">
                          Trọng số {comp.weight}%
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Coverage donut — P1 only */}
                {analysis.coverageData && (
                  <div className="flex items-center gap-4">
                    <div className="w-[120px] h-[120px] shrink-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[
                              { name: "Overlap", value: analysis.coverageData.overlap, color: COVERAGE_COLORS.overlap },
                              { name: "Chuyên gia", value: analysis.coverageData.unique, color: COVERAGE_COLORS.unique },
                              { name: "Lỗ hổng", value: analysis.coverageData.gap, color: COVERAGE_COLORS.gap },
                            ]}
                            cx="50%"
                            cy="50%"
                            innerRadius={35}
                            outerRadius={50}
                            dataKey="value"
                            strokeWidth={0}
                          >
                            {[COVERAGE_COLORS.overlap, COVERAGE_COLORS.unique, COVERAGE_COLORS.gap].map((color, idx) => (
                              <Cell key={idx} fill={color} />
                            ))}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COVERAGE_COLORS.overlap }} />
                        <span className="text-muted-foreground">Overlap:</span>
                        <span className="font-semibold text-foreground">{analysis.coverageData.overlap}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COVERAGE_COLORS.unique }} />
                        <span className="text-muted-foreground">Chuyên gia:</span>
                        <span className="font-semibold text-foreground">{analysis.coverageData.unique}</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: COVERAGE_COLORS.gap }} />
                        <span className="text-muted-foreground">Lỗ hổng:</span>
                        <span className="font-semibold text-foreground">{analysis.coverageData.gap}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Insight badges */}
                {analysis.insights.length > 0 && (
                  <div className="space-y-1.5">
                    {analysis.insights.map((ins, i) => (
                      <div key={i} className="flex items-start gap-2">
                        <InsightIcon type={ins.type} />
                        <span className={cn("text-xs leading-snug", insightTextClass(ins.type))}>
                          {ins.text}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Action items */}
                {analysis.actions.length > 0 && (
                  <div className="space-y-1.5">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                      Gợi ý
                    </p>
                    {analysis.actions.map((action, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <span
                          className={cn(
                            "text-[10px] font-semibold px-1.5 py-0.5 rounded border shrink-0",
                            priorityBadgeClass(action.priority)
                          )}
                        >
                          {action.priority === "high" ? "Cao" : action.priority === "medium" ? "Vừa" : "Thấp"}
                        </span>
                        <span className="text-xs text-muted-foreground">{action.text}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Fallback expanded content when no analysis loaded yet */}
            {isOpen && !analysis && phase.score !== null && (
              <div className="px-3 pb-3 border-t border-border pt-3">
                <p className="text-xs text-muted-foreground">
                  Đang tải dữ liệu phân tích...
                </p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
