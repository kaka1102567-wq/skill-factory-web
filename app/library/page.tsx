"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Download, Atom, Loader2, Package } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn, formatCost, formatNumber, formatTimeAgo } from "@/lib/utils";
import type { Build } from "@/types/build";

export default function LibraryPage() {
  const [builds, setBuilds] = useState<Build[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/builds?status=completed")
      .then((res) => res.json())
      .then((data) => {
        setBuilds(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Skills Library</h1>
        <p className="text-sm text-muted-foreground mt-1">
          All successfully built AI skills — download or view details.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
        </div>
      ) : builds.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
          <Package className="w-10 h-10 mb-3 opacity-50" />
          <p className="text-sm">No completed skills yet</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {builds.map((build) => (
            <div
              key={build.id}
              className="p-4 rounded-xl bg-card border border-border"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <Link
                    href={`/build/${build.id}`}
                    className="text-sm font-semibold text-foreground hover:text-indigo-400"
                  >
                    {build.name}
                  </Link>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {build.domain} &middot; {formatTimeAgo(build.created_at)}
                  </p>
                </div>
                {build.quality_score && (
                  <div
                    className={cn(
                      "w-10 h-10 rounded-full flex items-center justify-center border-2 text-xs font-bold",
                      build.quality_score >= 90
                        ? "border-emerald-500 text-emerald-400"
                        : build.quality_score >= 70
                          ? "border-amber-500 text-amber-400"
                          : "border-red-500 text-red-400"
                    )}
                  >
                    {Math.round(build.quality_score)}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3">
                <span className="flex items-center gap-1">
                  <Atom className="w-3 h-3" />
                  {formatNumber(
                    build.atoms_verified || build.atoms_extracted || 0
                  )}{" "}
                  atoms
                </span>
                <span>{formatCost(build.api_cost_usd)}</span>
              </div>
              {build.package_path && (
                <a href={`/api/builds/${build.id}/download`}>
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5 text-xs w-full"
                  >
                    <Download className="w-3 h-3" /> Download .zip
                  </Button>
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
