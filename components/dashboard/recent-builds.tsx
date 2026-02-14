"use client";

import { useState } from "react";
import { BuildCard } from "./build-card";
import { Button } from "@/components/ui/button";
import { Loader2, Inbox, AlertCircle, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useBuilds } from "@/hooks/use-builds";

const FILTER_OPTIONS: { value: string; label: string; emptyMsg: string }[] = [
  { value: "all", label: "All", emptyMsg: "No builds yet" },
  { value: "running", label: "Running", emptyMsg: "No builds running" },
  { value: "completed", label: "Completed", emptyMsg: "No completed builds" },
  { value: "failed", label: "Failed", emptyMsg: "No failed builds" },
];

const EMPTY_ICONS: Record<string, React.ReactNode> = {
  all: <Inbox className="w-10 h-10 mb-3 opacity-50" />,
  running: <Search className="w-10 h-10 mb-3 opacity-50" />,
  completed: <Inbox className="w-10 h-10 mb-3 opacity-50" />,
  failed: <AlertCircle className="w-10 h-10 mb-3 opacity-50" />,
};

export function RecentBuilds() {
  const [filter, setFilter] = useState("all");
  const { builds, loading } = useBuilds({ status: filter, refreshInterval: 10000 });

  const currentFilter = FILTER_OPTIONS.find((o) => o.value === filter)!;

  return (
    <div>
      {/* Filter tabs */}
      <div className="flex items-center gap-2 mb-4">
        {FILTER_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            variant={filter === opt.value ? "default" : "ghost"}
            size="sm"
            onClick={() => setFilter(opt.value)}
            className="text-xs gap-1.5"
          >
            {opt.label}
            {opt.value === "all" && builds.length > 0 && filter === "all" && (
              <Badge variant="secondary" className="ml-1 text-[10px] px-1.5 py-0">
                {builds.length}
              </Badge>
            )}
          </Button>
        ))}
      </div>

      {/* Build list */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="w-5 h-5 animate-spin mr-2" />
          <span className="text-sm">Loading...</span>
        </div>
      ) : builds.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          {EMPTY_ICONS[filter]}
          <p className="text-sm">{currentFilter.emptyMsg}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {builds.map((build) => (
            <BuildCard key={build.id} build={build} />
          ))}
        </div>
      )}
    </div>
  );
}
