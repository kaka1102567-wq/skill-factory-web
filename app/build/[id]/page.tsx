"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  RefreshCw,
  Square,
  Loader2,
  Clock,
  DollarSign,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  cn,
  formatCost,
  formatDuration,
  getStatusBgColor,
  getStatusLabel,
} from "@/lib/utils";
import { useBuildStream } from "@/hooks/use-build-stream";
import { PhaseStepper } from "@/components/build/phase-stepper";
import { LogViewer } from "@/components/build/log-viewer";
import { QualityReport } from "@/components/build/quality-report";
import { ConflictReview } from "@/components/build/conflict-review";
import type { Build } from "@/types/build";

export default function BuildDetailPage() {
  const params = useParams();
  const router = useRouter();
  const buildId = params.id as string;

  const [build, setBuild] = useState<Build | null>(null);
  const [loading, setLoading] = useState(true);
  const [showLogs, setShowLogs] = useState(true);
  const [conflicts, setConflicts] = useState<
    { id: string; atom_a: string; atom_b: string; source_a?: string; source_b?: string; baseline?: string }[]
  >([]);

  const { logs, phases, buildState, connected, finished } =
    useBuildStream(buildId);

  // Fetch initial build data
  useEffect(() => {
    fetch(`/api/builds/${buildId}`)
      .then((res) => {
        if (!res.ok) {
          router.push("/");
          return null;
        }
        return res.json();
      })
      .then((data) => {
        if (!data || data.error) {
          router.push("/");
          return;
        }
        setBuild(data);
        if (data.review_data) {
          try {
            setConflicts(JSON.parse(data.review_data));
          } catch {
            // Invalid JSON
          }
        }
        setLoading(false);
      })
      .catch(() => router.push("/"));
  }, [buildId, router]);

  // Update build from SSE state
  useEffect(() => {
    if (buildState && build) {
      setBuild((prev) => (prev ? { ...prev, ...buildState } : prev));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildState]);

  // Refresh build data when finished
  useEffect(() => {
    if (finished) {
      fetch(`/api/builds/${buildId}`)
        .then((res) => res.json())
        .then(setBuild)
        .catch(() => {});
    }
  }, [finished, buildId]);

  const handleStop = async () => {
    try {
      await fetch(`/api/builds/${buildId}/stop`, { method: "POST" });
      const res = await fetch(`/api/builds/${buildId}`);
      if (res.ok) setBuild(await res.json());
    } catch {
      // Network error — ignore, SSE will update state
    }
  };

  const handleRetry = async () => {
    if (!build) return;
    try {
      const res = await fetch(`/api/builds/${buildId}/retry`, { method: "POST" });
      if (!res.ok) return;
      const result = await res.json();
      router.push(`/build/${result.id}`);
    } catch {
      // Network error
    }
  };

  if (loading || !build) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isActive = ["running", "queued"].includes(build.status);
  const isComplete = build.status === "completed";
  const isFailed = build.status === "failed";
  const isPaused = build.status === "paused";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-foreground">
                {build.name}
              </h1>
              <Badge
                variant="outline"
                className={cn(
                  "text-xs border",
                  getStatusBgColor(build.status)
                )}
              >
                {getStatusLabel(build.status)}
              </Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
              <span>{build.domain}</span>
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {formatDuration(build.started_at, build.completed_at)}
              </span>
              <span className="flex items-center gap-1">
                <DollarSign className="w-3 h-3" />
                {formatCost(build.api_cost_usd)}
              </span>
              {isActive && (
                <span
                  className={cn(
                    "flex items-center gap-1",
                    connected ? "text-emerald-400" : "text-red-400"
                  )}
                >
                  {connected ? (
                    <Wifi className="w-3 h-3" />
                  ) : (
                    <WifiOff className="w-3 h-3" />
                  )}
                  {connected ? "Live" : "Disconnected"}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          {isActive && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleStop}
              className="gap-1.5"
            >
              <Square className="w-3.5 h-3.5" /> Stop
            </Button>
          )}
          {isFailed && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRetry}
              className="gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry
            </Button>
          )}
          {isComplete && build.package_path && (
            <a href={`/api/builds/${buildId}/download`}>
              <Button size="sm" className="gap-1.5">
                <Download className="w-3.5 h-3.5" /> Download .zip
              </Button>
            </a>
          )}
        </div>
      </div>

      {/* SSE Disconnected Banner */}
      {isActive && !connected && (
        <div className="p-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-xs text-yellow-400 flex items-center gap-2">
          <WifiOff className="w-3.5 h-3.5" />
          Mất kết nối live stream. Đang tự động kết nối lại...
        </div>
      )}

      {/* Error Message */}
      {isFailed && build.error_message && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
          {build.error_message}
        </div>
      )}

      {/* Conflict Review */}
      {isPaused && conflicts.length > 0 && (
        <ConflictReview
          buildId={buildId}
          conflicts={conflicts}
          onComplete={() => {
            fetch(`/api/builds/${buildId}`)
              .then((r) => r.json())
              .then(setBuild);
          }}
        />
      )}

      {/* Main Content — 2 column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Phase Stepper */}
        <div className="lg:col-span-1">
          <div className="p-4 rounded-xl bg-card border border-border">
            <PhaseStepper phases={phases} />
          </div>
        </div>

        {/* Right: Logs or Quality Report */}
        <div className="lg:col-span-2">
          {isComplete && (
            <div className="space-y-4">
              <QualityReport build={build} phases={phases} />
              <div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowLogs(!showLogs)}
                  className="text-xs mb-2"
                >
                  {showLogs ? "Hide logs" : "Show logs"} ({logs.length} entries)
                </Button>
                {showLogs && (
                  <div className="rounded-xl border border-border overflow-hidden">
                    <LogViewer logs={logs} />
                  </div>
                )}
              </div>
            </div>
          )}

          {(isActive || isPaused || isFailed) && (
            <div className="rounded-xl border border-border overflow-hidden relative">
              <LogViewer logs={logs} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
