"use client";

import { useEffect, useState } from "react";
import { Atom, DollarSign, Clock, TrendingUp, CheckCircle, XCircle } from "lucide-react";
import { cn, formatCost, formatNumber, formatDuration } from "@/lib/utils";
import type { Build } from "@/types/build";
import type { PhaseState } from "@/hooks/use-build-stream";

interface SmokeTest {
  prompt: string;
  passed: boolean;
  score?: number;
  grade_notes?: string;
}

interface SmokeReport {
  results?: SmokeTest[];
  pass_count?: number;
  total?: number;
  score?: number;
  passed?: boolean;
}

interface P6Report {
  best_train_score?: number;
  best_test_score?: number;
  iterations?: number;
}

export function QualityReport({
  build,
  phases,
}: {
  build: Build;
  phases: PhaseState[];
}) {
  const phasesWithScores = phases.filter((p) => p.score !== null);
  const [smokeReport, setSmokeReport] = useState<SmokeReport | null>(null);
  const [p6Report, setP6Report] = useState<P6Report | null>(null);

  useEffect(() => {
    if (!build.id || build.status !== "completed") return;
    const base = `/api/builds/${build.id}/reports`;
    fetch(`${base}?file=smoke_test_report.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setSmokeReport(d))
      .catch(() => {});
    fetch(`${base}?file=p6_optimization_report.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setP6Report(d))
      .catch(() => {});
  }, [build.id, build.status]);

  return (
    <div className="space-y-4">
      {/* Overall Score */}
      {build.quality_score && (
        <div className="flex items-center gap-4 p-4 rounded-xl bg-card border border-border">
          <div
            className={cn(
              "w-16 h-16 rounded-full flex items-center justify-center border-4",
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
              Quality Score
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
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          icon={Atom}
          label="Atoms"
          value={formatNumber(
            build.atoms_verified || build.atoms_extracted || 0
          )}
          detail={
            build.atoms_extracted
              ? `${build.atoms_extracted} → ${build.atoms_deduplicated || "?"} → ${build.atoms_verified || "?"}`
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

      {/* Phase Scores */}
      {phasesWithScores.length > 0 && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Quality Gates per Phase
          </h4>
          <div className="grid grid-cols-3 lg:grid-cols-6 gap-2">
            {phases.map((p) => (
              <div key={p.id} className="text-center">
                <p className="text-xs text-muted-foreground mb-1">{p.name}</p>
                <div
                  className={cn(
                    "text-lg font-bold",
                    p.score === null
                      ? "text-muted-foreground"
                      : p.score >= 80
                        ? "text-emerald-400"
                        : p.score >= 60
                          ? "text-amber-400"
                          : "text-red-400"
                  )}
                >
                  {p.score !== null ? Math.round(p.score) : "—"}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Smoke Tests */}
      {smokeReport && smokeReport.results && smokeReport.results.length > 0 && (
        <div className="p-4 rounded-xl bg-card border border-border">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            Smoke Tests ({smokeReport.pass_count ?? 0} passed
            {((smokeReport.total ?? 0) - (smokeReport.pass_count ?? 0)) > 0 && (
              <span className="text-red-400"> · {(smokeReport.total ?? 0) - (smokeReport.pass_count ?? 0)} failed</span>
            )}
            )
          </h4>
          <div className="space-y-1.5">
            {smokeReport.results.map((t, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                {t.passed ? (
                  <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                )}
                <span className={t.passed ? "text-foreground" : "text-red-400"}>
                  {t.prompt}
                </span>
                {t.grade_notes && (
                  <span className="text-xs text-muted-foreground truncate">
                    — {t.grade_notes}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
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
