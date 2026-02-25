"use client";

import { cn, formatCost, formatNumber } from "@/lib/utils";
import type { Build } from "@/types/build";

interface CompareData {
  a: Build & { description: string; p6_report: Record<string, unknown> | null };
  b: Build & { description: string; p6_report: Record<string, unknown> | null };
}

const METRICS: {
  key: keyof Build;
  label: string;
  format: (v: unknown) => string;
  higherIsBetter: boolean;
}[] = [
  {
    key: "quality_score",
    label: "Quality Score",
    format: (v) => (v != null ? `${Math.round(v as number)}` : "—"),
    higherIsBetter: true,
  },
  {
    key: "atoms_verified",
    label: "Atoms Verified",
    format: (v) => (v != null ? formatNumber(v as number) : "—"),
    higherIsBetter: true,
  },
  {
    key: "api_cost_usd",
    label: "API Cost",
    format: (v) => (v != null ? formatCost(v as number) : "—"),
    higherIsBetter: false, // lower is better
  },
  {
    key: "tokens_used",
    label: "Tokens Used",
    format: (v) => (v != null ? formatNumber(v as number) : "—"),
    higherIsBetter: false,
  },
];

export function BuildCompare({ data }: { data: CompareData }) {
  const { a, b } = data;

  return (
    <div className="space-y-4">
      {/* Build names header */}
      <div className="grid grid-cols-3 gap-3">
        <div /> {/* spacer */}
        <BuildHeader build={a} label="A" />
        <BuildHeader build={b} label="B" />
      </div>

      {/* Metric rows */}
      <div className="rounded-xl bg-card border border-border overflow-hidden">
        <div className="px-4 py-2 border-b border-border bg-muted/30">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Metrics
          </p>
        </div>
        {METRICS.map((metric) => {
          const valA = a[metric.key] as number | null | undefined;
          const valB = b[metric.key] as number | null | undefined;
          const colorA = getColor(valA, valB, metric.higherIsBetter);
          const colorB = getColor(valB, valA, metric.higherIsBetter);
          return (
            <div
              key={metric.key}
              className="grid grid-cols-3 gap-3 px-4 py-3 border-b border-border last:border-0 items-center"
            >
              <span className="text-xs text-muted-foreground">{metric.label}</span>
              <span className={cn("text-sm font-semibold text-center", colorA)}>
                {metric.format(valA)}
              </span>
              <span className={cn("text-sm font-semibold text-center", colorB)}>
                {metric.format(valB)}
              </span>
            </div>
          );
        })}
      </div>

      {/* Description comparison */}
      {(a.description || b.description) && (
        <div className="rounded-xl bg-card border border-border overflow-hidden">
          <div className="px-4 py-2 border-b border-border bg-muted/30">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Description
            </p>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-border">
            <div className="p-4">
              <p className="text-xs font-semibold text-indigo-400 mb-1.5">Build A</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {a.description || "—"}
              </p>
            </div>
            <div className="p-4">
              <p className="text-xs font-semibold text-violet-400 mb-1.5">Build B</p>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {b.description || "—"}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function BuildHeader({
  build,
  label,
}: {
  build: Build & { description: string };
  label: string;
}) {
  return (
    <div className="p-3 rounded-lg bg-card border border-border text-center">
      <p className="text-xs text-muted-foreground mb-0.5">Build {label}</p>
      <p className="text-sm font-semibold text-foreground truncate">{build.name}</p>
      <p className="text-xs text-muted-foreground">{build.domain}</p>
    </div>
  );
}

function getColor(
  mine: number | null | undefined,
  other: number | null | undefined,
  higherIsBetter: boolean
): string {
  if (mine == null || other == null) return "text-foreground";
  if (mine === other) return "text-foreground";
  const isBetter = higherIsBetter ? mine > other : mine < other;
  return isBetter ? "text-emerald-400" : "text-red-400";
}
