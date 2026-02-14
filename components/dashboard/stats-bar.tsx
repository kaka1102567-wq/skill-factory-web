"use client";

import { useEffect, useState, useCallback } from "react";
import { BarChart3, Target, Atom, DollarSign, Activity } from "lucide-react";
import { formatCost, formatNumber } from "@/lib/utils";
import type { DashboardStats } from "@/types/build";

interface ExtendedStats extends DashboardStats {
  active_running?: number;
  queue_length?: number;
}

const STAT_CARDS = [
  { key: "total_builds", label: "Total builds", icon: BarChart3, color: "text-blue-400", bg: "bg-blue-500/10", format: (v: number) => v.toString() },
  { key: "avg_quality", label: "Avg quality", icon: Target, color: "text-emerald-400", bg: "bg-emerald-500/10", format: (v: number | null) => v ? `${v}%` : "\u2014" },
  { key: "total_atoms", label: "Total atoms", icon: Atom, color: "text-purple-400", bg: "bg-purple-500/10", format: (v: number) => formatNumber(v) },
  { key: "total_cost", label: "Total cost", icon: DollarSign, color: "text-amber-400", bg: "bg-amber-500/10", format: (v: number) => formatCost(v) },
] as const;

export function StatsBar() {
  const [stats, setStats] = useState<ExtendedStats | null>(null);

  const fetchStats = useCallback(() => {
    fetch("/api/stats")
      .then((res) => res.json())
      .then(setStats)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const running = stats?.active_running ?? 0;
  const queued = stats?.queue_length ?? 0;

  return (
    <div className="space-y-3">
      {/* Live indicator */}
      {running > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
          <Activity className="w-4 h-4 text-indigo-400 animate-pulse" />
          <span className="text-xs text-indigo-300">
            {running} build(s) running{queued > 0 ? `, ${queued} queued` : ""}
          </span>
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {STAT_CARDS.map((card) => {
          const Icon = card.icon;
          const value = stats ? stats[card.key as keyof DashboardStats] : null;
          return (
            <div key={card.key} className="p-4 rounded-xl bg-card border border-border">
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-7 h-7 rounded-lg ${card.bg} flex items-center justify-center`}>
                  <Icon className={`w-3.5 h-3.5 ${card.color}`} />
                </div>
                <span className="text-xs text-muted-foreground">{card.label}</span>
              </div>
              <p className="text-2xl font-bold text-foreground">
                {stats ? card.format(value as number) : "\u2014"}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
