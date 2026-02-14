"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Check,
  X,
  Merge,
  Trash2,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface Conflict {
  id: string;
  atom_a: string;
  atom_b: string;
  source_a?: string;
  source_b?: string;
  baseline?: string;
}

type Resolution = "keep_a" | "keep_b" | "merge" | "discard";

interface ConflictReviewProps {
  buildId: string;
  conflicts: Conflict[];
  onComplete: () => void;
}

export function ConflictReview({
  buildId,
  conflicts,
  onComplete,
}: ConflictReviewProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [resolutions, setResolutions] = useState<Record<string, Resolution>>(
    {}
  );
  const [submitting, setSubmitting] = useState(false);

  const current = conflicts[currentIndex];
  const resolvedCount = Object.keys(resolutions).length;
  const allResolved = resolvedCount === conflicts.length;

  const resolve = (resolution: Resolution) => {
    setResolutions((prev) => ({ ...prev, [current.id]: resolution }));
    // Auto-advance to next conflict
    if (currentIndex < conflicts.length - 1) {
      setTimeout(() => setCurrentIndex((i) => i + 1), 300);
    }
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      await fetch(`/api/builds/${buildId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolutions }),
      });
      onComplete();
    } catch {
      // Error silently handled
    }
    setSubmitting(false);
  };

  if (!current) return null;

  return (
    <div className="p-5 rounded-xl bg-card border border-amber-500/30">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-5 h-5 text-amber-400" />
        <h3 className="text-sm font-semibold text-foreground">
          {conflicts.length} conflicts need review
        </h3>
        <span className="text-xs text-muted-foreground ml-auto">
          Build paused at P3
        </span>
      </div>

      {/* Progress */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
          <span>Reviewed</span>
          <span>
            {resolvedCount}/{conflicts.length}
          </span>
        </div>
        <Progress
          value={(resolvedCount / conflicts.length) * 100}
          className="h-1.5"
        />
      </div>

      {/* Current Conflict */}
      <div className="mb-4">
        <p className="text-xs text-muted-foreground mb-3">
          Conflict {currentIndex + 1} of {conflicts.length}
        </p>
        <div className="grid grid-cols-2 gap-3">
          {/* Atom A */}
          <div
            className={cn(
              "p-3 rounded-lg border",
              resolutions[current.id] === "keep_a"
                ? "border-emerald-500 bg-emerald-500/5"
                : "border-border"
            )}
          >
            <Badge variant="outline" className="text-xs mb-2">
              Atom A
            </Badge>
            <p className="text-sm text-foreground">{current.atom_a}</p>
            {current.source_a && (
              <p className="text-xs text-muted-foreground mt-2">
                {current.source_a}
              </p>
            )}
          </div>

          {/* Atom B */}
          <div
            className={cn(
              "p-3 rounded-lg border",
              resolutions[current.id] === "keep_b"
                ? "border-emerald-500 bg-emerald-500/5"
                : "border-border"
            )}
          >
            <Badge variant="outline" className="text-xs mb-2">
              Atom B
            </Badge>
            <p className="text-sm text-foreground">{current.atom_b}</p>
            {current.source_b && (
              <p className="text-xs text-muted-foreground mt-2">
                {current.source_b}
              </p>
            )}
          </div>
        </div>

        {/* Baseline reference */}
        {current.baseline && (
          <div className="mt-3 p-3 rounded-lg bg-indigo-500/5 border border-indigo-500/20">
            <p className="text-xs font-semibold text-indigo-400 mb-1">
              Official Docs (Baseline):
            </p>
            <p className="text-xs text-muted-foreground">{current.baseline}</p>
          </div>
        )}
      </div>

      {/* Resolution Buttons */}
      <div className="flex gap-2 mb-4">
        <Button
          variant={resolutions[current.id] === "keep_a" ? "default" : "outline"}
          size="sm"
          onClick={() => resolve("keep_a")}
          className="gap-1.5 text-xs"
        >
          <Check className="w-3 h-3" /> Keep A
        </Button>
        <Button
          variant={resolutions[current.id] === "keep_b" ? "default" : "outline"}
          size="sm"
          onClick={() => resolve("keep_b")}
          className="gap-1.5 text-xs"
        >
          <Check className="w-3 h-3" /> Keep B
        </Button>
        <Button
          variant={resolutions[current.id] === "merge" ? "default" : "outline"}
          size="sm"
          onClick={() => resolve("merge")}
          className="gap-1.5 text-xs"
        >
          <Merge className="w-3 h-3" /> Merge
        </Button>
        <Button
          variant={
            resolutions[current.id] === "discard" ? "destructive" : "outline"
          }
          size="sm"
          onClick={() => resolve("discard")}
          className="gap-1.5 text-xs"
        >
          <Trash2 className="w-3 h-3" /> Discard
        </Button>
      </div>

      {/* Navigation + Submit */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((i) => i - 1)}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={currentIndex === conflicts.length - 1}
            onClick={() => setCurrentIndex((i) => i + 1)}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>

        <Button onClick={submit} disabled={!allResolved || submitting} className="gap-2">
          {submitting ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Submitting...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" /> Submit & Resume Build
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
