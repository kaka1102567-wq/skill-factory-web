"use client";

import { useEffect, useState } from "react";
import { Atom, DollarSign, Clock, TrendingUp } from "lucide-react";
import { cn, formatCost, formatNumber, formatDuration } from "@/lib/utils";
import type { Build } from "@/types/build";
import type { PhaseState } from "@/hooks/use-build-stream";
import { SmokeTestDetail, type SmokeReport } from "./smoke-test-detail";
import { PhaseInsights } from "./phase-insights";

interface P6Report {
  best_train_score?: number;
  best_test_score?: number;
  iterations?: number;
}

interface FinalScoreBreakdown {
  pipeline_score: number;
  smoke_test_avg: number;
  trigger_test_score: number;
}

export function QualityReport({
  build,
  phases,
}: {
  build: Build;
  phases: PhaseState[];
}) {
  const [smokeReport, setSmokeReport] = useState<SmokeReport | null>(null);
  const [p6Report, setP6Report] = useState<P6Report | null>(null);
  const [breakdown, setBreakdown] = useState<FinalScoreBreakdown | null>(null);

  useEffect(() => {
    if (!build.id || build.status !== "completed") return;
    const base = `/api/builds/${build.id}/reports`;
    fetch(`${base}?file=smoke_test_report.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        setSmokeReport(d);
        // Derive breakdown from available data
        if (d) computeBreakdown(d);
      })
      .catch(() => {});
    fetch(`${base}?file=p6_optimization_report.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setP6Report(d))
      .catch(() => {});
  }, [build.id, build.status]);

  // Compute breakdown from smoke + p6 + pipeline phases
  function computeBreakdown(smoke: SmokeReport | null) {
    // Pipeline score: from P5 phase result
    const p5Phase = phases.find((p) => p.id === "p5");
    const pipelineScore = p5Phase?.score ?? build.quality_score ?? 0;
    const smokeAvg = smoke?.score != null ? smoke.score * 100 : 0;
    // trigger score computed when p6Report is available (via separate effect)
    setBreakdown({ pipeline_score: pipelineScore, smoke_test_avg: smokeAvg, trigger_test_score: 0 });
  }

  // Update trigger score when p6Report loads
  useEffect(() => {
    if (!p6Report || !breakdown) return;
    const triggerScore = (p6Report.best_test_score ?? 0) * 100;
    if (triggerScore !== breakdown.trigger_test_score) {
      setBreakdown((prev) => prev ? { ...prev, trigger_test_score: triggerScore } : prev);
    }
  }, [p6Report, breakdown]);

  return (
    <div className="space-y-4">
      {/* Final Score */}
      {build.quality_score && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <div className="flex items-center gap-4">
            <div
              className={cn(
                "w-16 h-16 rounded-full flex items-center justify-center border-4 shrink-0",
                build.quality_score >= 90
                  ? "border-emerald-500 text-emerald-400"
                  : build.quality_score >= 70
                    ? "border-amber-500 text-amber-400"
                    : "border-red-500 text-red-400"
              )}
            >
              <span className="text-xl font-bold">
                {Math.round(build.quality_score)}
              </span>
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                Final Score
              </p>
              <p className="text-xs text-muted-foreground">
                {build.quality_score >= 90
                  ? "Excellent — Ready for production"
                  : build.quality_score >= 70
                    ? "Good — Usable, review recommended"
                    : "Needs improvement — Review carefully"}
              </p>
            </div>
          </div>
          {/* Breakdown bar */}
          {breakdown && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-[10px] text-muted-foreground mb-2 font-mono">
                Pipeline×0.6 + Smoke×0.3 + Trigger×0.1
              </p>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-[10px] text-muted-foreground">Pipeline</p>
                  <p className="text-sm font-bold text-foreground">
                    {Math.round(breakdown.pipeline_score)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">×0.6</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Smoke Test</p>
                  <p className="text-sm font-bold text-foreground">
                    {Math.round(breakdown.smoke_test_avg)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">×0.3</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Trigger</p>
                  <p className="text-sm font-bold text-foreground">
                    {Math.round(breakdown.trigger_test_score)}
                  </p>
                  <p className="text-[10px] text-muted-foreground">×0.1</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          icon={Atom}
          label="Atoms"
          value={formatNumber(
            build.atoms_deduplicated || build.atoms_extracted || 0
          )}
          detail={
            build.atoms_extracted
              ? `${build.atoms_extracted} extracted → ${build.atoms_deduplicated || "?"} deduped` +
                (build.atoms_verified != null ? ` (${build.atoms_verified} verified)` : "")
              : undefined
          }
          color="text-purple-400"
        />
        <StatCard
          icon={TrendingUp}
          label="Compression"
          value={
            build.compression_ratio
              ? `${Math.round((1 - build.compression_ratio) * 100)}%`
              : "—"
          }
          detail="Data compression ratio"
          color="text-cyan-400"
        />
        <StatCard
          icon={DollarSign}
          label="Cost"
          value={formatCost(build.api_cost_usd)}
          detail={
            build.tokens_used
              ? `${formatNumber(build.tokens_used)} tokens`
              : undefined
          }
          color="text-amber-400"
        />
        <StatCard
          icon={Clock}
          label="Duration"
          value={formatDuration(build.started_at, build.completed_at)}
          color="text-blue-400"
        />
      </div>

      {/* Phase Insights Dashboard */}
      <PhaseInsights buildId={build.id} phases={phases} buildStatus={build.status} />

      {/* Smoke Tests */}
      {smokeReport && smokeReport.results && smokeReport.results.length > 0 && (
        <SmokeTestDetail report={smokeReport} />
      )}

      {/* P6 Optimization */}
      {p6Report && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            P6 Trigger Optimization
          </h4>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="text-xs text-muted-foreground mb-1">Train</p>
              <p className={cn(
                "text-lg font-bold",
                (p6Report.best_train_score ?? 0) >= 0.9 ? "text-emerald-400"
                  : (p6Report.best_train_score ?? 0) >= 0.7 ? "text-amber-400"
                  : "text-red-400"
              )}>
                {p6Report.best_train_score != null
                  ? `${Math.round(p6Report.best_train_score * 100)}%`
                  : "—"}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground mb-1">Test</p>
              <p className={cn(
                "text-lg font-bold",
                (p6Report.best_test_score ?? 0) >= 0.9 ? "text-emerald-400"
                  : (p6Report.best_test_score ?? 0) >= 0.7 ? "text-amber-400"
                  : "text-red-400"
              )}>
                {p6Report.best_test_score != null
                  ? `${Math.round(p6Report.best_test_score * 100)}%`
                  : "—"}
              </p>
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground mb-1">Iterations</p>
              <p className="text-lg font-bold text-blue-400">
                {p6Report.iterations ?? "—"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail?: string;
  color: string;
}) {
  return (
    <div className="p-3 rounded-lg bg-card border border-border">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className={cn("w-3.5 h-3.5", color)} />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className="text-lg font-bold text-foreground">{value}</p>
      {detail && (
        <p className="text-xs text-muted-foreground mt-0.5">{detail}</p>
      )}
    </div>
  );
}
