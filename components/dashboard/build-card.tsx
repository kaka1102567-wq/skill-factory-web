"use client";

import Link from "next/link";
import { Clock, DollarSign, Atom, ArrowRight, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  cn, formatCost, formatDuration, formatTimeAgo,
  getStatusBgColor, getStatusLabel, getOverallProgress, getPhaseLabel
} from "@/lib/utils";
import type { Build } from "@/types/build";

interface BuildCardProps {
  build: Build;
  onDelete?: (id: string) => void;
}

export function BuildCard({ build, onDelete }: BuildCardProps) {
  const progress = getOverallProgress(build.current_phase, build.phase_progress);
  const canDelete = onDelete && !["running", "queued"].includes(build.status);

  return (
    <div className="group relative">
      <Link href={`/build/${build.id}`} className="block">
        <div className="p-4 rounded-xl bg-card border border-border hover:border-indigo-500/30 transition-all">
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-foreground truncate group-hover:text-indigo-400 transition-colors">
                {build.name}
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                {build.domain} • {formatTimeAgo(build.created_at)}
              </p>
            </div>
            <Badge variant="outline" className={cn("ml-2 text-xs border", getStatusBgColor(build.status))}>
              {getStatusLabel(build.status)}
            </Badge>
          </div>

          {/* Progress bar */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-muted-foreground">
                {build.current_phase
                  ? `Phase: ${getPhaseLabel(build.current_phase)}`
                  : build.status === "completed"
                  ? "Complete"
                  : "\u2014"}
              </span>
              <span className="text-xs font-mono text-muted-foreground">
                {build.status === "completed" ? "100%" : `${progress}%`}
              </span>
            </div>
            <Progress
              value={build.status === "completed" ? 100 : progress}
              className="h-1.5"
            />
          </div>

          {/* Footer stats */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            {build.quality_score && (
              <span className="text-emerald-400 font-semibold">
                {Math.round(build.quality_score)}%
              </span>
            )}
            {(build.atoms_verified || build.atoms_extracted) && (
              <span className="flex items-center gap-1">
                <Atom className="w-3 h-3" />
                {build.atoms_verified || build.atoms_extracted}
              </span>
            )}
            <span className="flex items-center gap-1">
              <DollarSign className="w-3 h-3" />
              {formatCost(build.api_cost_usd)}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatDuration(build.started_at, build.completed_at)}
            </span>
            <ArrowRight className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-indigo-400" />
          </div>
        </div>
      </Link>

      {/* Delete button — hover overlay */}
      {canDelete && (
        <div className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button
                onClick={(e) => e.preventDefault()}
                className="p-1.5 rounded-md bg-zinc-800/80 hover:bg-red-900/80 text-zinc-500 hover:text-red-400 transition-colors backdrop-blur-sm"
                title="Delete build"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete build?</AlertDialogTitle>
                <AlertDialogDescription>
                  Build &ldquo;{build.name}&rdquo; will be permanently deleted,
                  including all output files and logs. This cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => onDelete(build.id)}
                  className="bg-red-600 hover:bg-red-700"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      )}
    </div>
  );
}
