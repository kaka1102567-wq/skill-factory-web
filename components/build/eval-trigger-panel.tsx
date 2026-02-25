"use client";

import { useEffect, useState } from "react";
import { CheckCircle, XCircle, Loader2, Target, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface EvalQuery {
  query: string;
  should_trigger: boolean;
  result?: boolean;
}

interface EvalReport {
  best_description: string;
  original_description: string;
  best_train_score: number;
  best_test_score: number;
  iterations: number;
  eval_set: EvalQuery[];
}

interface EvalTriggerData {
  eval_set: EvalQuery[];
  report: EvalReport | null;
}

export function EvalTriggerPanel({ buildId }: { buildId: string }) {
  const [data, setData] = useState<EvalTriggerData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/builds/${buildId}/eval-trigger`)
      .then((res) => res.json())
      .then(setData)
      .catch(() => setData({ eval_set: [], report: null }))
      .finally(() => setLoading(false));
  }, [buildId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data?.report) {
    return (
      <div className="p-6 rounded-xl bg-card border border-border text-center">
        <Target className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">
          No trigger optimization data — run P6 to generate eval report.
        </p>
      </div>
    );
  }

  const { report, eval_set } = data;
  const trainPct = Math.round(report.best_train_score * 100);
  const testPct = Math.round(report.best_test_score * 100);

  // Attach result to eval_set entries (last history iteration results if present)
  const queries: (EvalQuery & { correct: boolean })[] = eval_set.map((q) => {
    const correct = q.result !== undefined
      ? q.result === q.should_trigger
      : true; // no result data means we don't know
    return { ...q, correct };
  });

  return (
    <div className="space-y-4">
      {/* Metric Cards */}
      <div className="grid grid-cols-3 gap-3">
        <MetricCard
          label="Train Score"
          value={`${trainPct}%`}
          color={trainPct >= 90 ? "text-emerald-400" : trainPct >= 70 ? "text-amber-400" : "text-red-400"}
          icon={TrendingUp}
        />
        <MetricCard
          label="Test Score"
          value={`${testPct}%`}
          color={testPct >= 90 ? "text-emerald-400" : testPct >= 70 ? "text-amber-400" : "text-red-400"}
          icon={Target}
        />
        <MetricCard
          label="Iterations"
          value={String(report.iterations)}
          color="text-blue-400"
          icon={TrendingUp}
        />
      </div>

      {/* Description Comparison */}
      {report.original_description !== report.best_description && (
        <div className="rounded-xl bg-card border border-border overflow-hidden">
          <div className="px-4 py-2 border-b border-border bg-muted/30">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Description Change
            </p>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-border">
            <DescSection label="Before" text={report.original_description} />
            <DescSection label="After" text={report.best_description} highlight />
          </div>
        </div>
      )}

      {/* Eval Queries Table */}
      {queries.length > 0 && (
        <div className="rounded-xl bg-card border border-border overflow-hidden">
          <div className="px-4 py-2 border-b border-border bg-muted/30">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Eval Queries ({queries.length})
            </p>
          </div>
          <div className="divide-y divide-border">
            {queries.map((q, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-4 py-2.5 text-sm"
              >
                <span
                  className={cn(
                    "text-xs font-mono px-1.5 py-0.5 rounded shrink-0",
                    q.should_trigger
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-zinc-500/10 text-zinc-400"
                  )}
                >
                  {q.should_trigger ? "Y" : "N"}
                </span>
                <span className="flex-1 text-muted-foreground truncate">
                  {q.query}
                </span>
                {q.result !== undefined ? (
                  q.correct ? (
                    <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400 shrink-0" />
                  )
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
  icon: Icon,
}: {
  label: string;
  value: string;
  color: string;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="p-3 rounded-lg bg-card border border-border">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className={cn("w-3.5 h-3.5", color)} />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p className={cn("text-xl font-bold", color)}>{value}</p>
    </div>
  );
}

function DescSection({
  label,
  text,
  highlight,
}: {
  label: string;
  text: string;
  highlight?: boolean;
}) {
  return (
    <div className="p-4">
      <p
        className={cn(
          "text-xs font-semibold mb-1.5",
          highlight ? "text-emerald-400" : "text-muted-foreground"
        )}
      >
        {label}
      </p>
      <p className="text-sm text-foreground leading-relaxed">{text}</p>
    </div>
  );
}
