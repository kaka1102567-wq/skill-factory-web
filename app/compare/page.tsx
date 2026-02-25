"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, GitCompare } from "lucide-react";
import { BuildCompare } from "@/components/build/build-compare";
import type { Build } from "@/types/build";

type CompareData = {
  a: Build & { description: string; p6_report: Record<string, unknown> | null };
  b: Build & { description: string; p6_report: Record<string, unknown> | null };
};

export default function ComparePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [builds, setBuilds] = useState<Build[]>([]);
  const [selectedA, setSelectedA] = useState(searchParams.get("a") || "");
  const [selectedB, setSelectedB] = useState(searchParams.get("b") || "");
  const [compareData, setCompareData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(false);
  const [buildsLoading, setBuildsLoading] = useState(true);

  // Fetch completed builds for selectors
  useEffect(() => {
    fetch("/api/builds?status=completed")
      .then((r) => r.json())
      .then((data) => setBuilds(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setBuildsLoading(false));
  }, []);

  const fetchCompare = useCallback(
    async (a: string, b: string) => {
      if (!a || !b) return;
      setLoading(true);
      setCompareData(null);
      try {
        const res = await fetch(`/api/builds/compare?a=${a}&b=${b}`);
        if (!res.ok) return;
        const data = await res.json();
        setCompareData(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Sync URL params on selection change
  useEffect(() => {
    if (!selectedA && !selectedB) return;
    const params = new URLSearchParams();
    if (selectedA) params.set("a", selectedA);
    if (selectedB) params.set("b", selectedB);
    router.replace(`/compare?${params.toString()}`, { scroll: false });

    if (selectedA && selectedB) {
      fetchCompare(selectedA, selectedB);
    } else {
      setCompareData(null);
    }
  }, [selectedA, selectedB, router, fetchCompare]);

  const completedBuilds = builds.filter((b) => b.status === "completed");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-foreground">Compare Builds</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Side-by-side comparison of two completed builds.
        </p>
      </div>

      {/* Selectors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BuildSelector
          label="Build A"
          value={selectedA}
          onChange={setSelectedA}
          builds={completedBuilds}
          loading={buildsLoading}
          exclude={selectedB}
          accent="text-indigo-400"
        />
        <BuildSelector
          label="Build B"
          value={selectedB}
          onChange={setSelectedB}
          builds={completedBuilds}
          loading={buildsLoading}
          exclude={selectedA}
          accent="text-violet-400"
        />
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Empty state */}
      {!loading && !compareData && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <GitCompare className="w-10 h-10 text-muted-foreground mb-3" />
          <p className="text-sm text-muted-foreground">
            {completedBuilds.length < 2
              ? "Need at least 2 completed builds to compare."
              : "Select two builds above to compare them."}
          </p>
        </div>
      )}

      {/* Compare result */}
      {!loading && compareData && <BuildCompare data={compareData} />}
    </div>
  );
}

function BuildSelector({
  label,
  value,
  onChange,
  builds,
  loading,
  exclude,
  accent,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  builds: Build[];
  loading: boolean;
  exclude: string;
  accent: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className={`text-xs font-semibold ${accent}`}>{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
        className="w-full px-3 py-2 rounded-lg bg-card border border-border text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
      >
        <option value="">— Select a build —</option>
        {builds
          .filter((b) => b.id !== exclude)
          .map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} ({b.domain}){" "}
              {b.quality_score ? `· ${Math.round(b.quality_score)}%` : ""}
            </option>
          ))}
      </select>
    </div>
  );
}
