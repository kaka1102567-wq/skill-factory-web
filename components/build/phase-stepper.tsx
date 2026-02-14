import { Check, Loader2, Circle, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import type { PhaseState } from "@/hooks/use-build-stream";
import { PHASES } from "@/types/build";

const PHASE_COLORS: Record<string, string> = {
  p0: "text-indigo-400 border-indigo-400",
  p1: "text-amber-400 border-amber-400",
  p2: "text-emerald-400 border-emerald-400",
  p3: "text-purple-400 border-purple-400",
  p4: "text-red-400 border-red-400",
  p5: "text-cyan-400 border-cyan-400",
};

export function PhaseStepper({ phases }: { phases: PhaseState[] }) {
  return (
    <div className="space-y-1">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
        Pipeline Progress
      </h3>
      {phases.map((phase, idx) => {
        const meta = PHASES.find((p) => p.id === phase.id);
        const isLast = idx === phases.length - 1;

        return (
          <div key={phase.id} className="flex gap-3">
            {/* Icon column */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "w-7 h-7 rounded-full flex items-center justify-center border-2 transition-all",
                  phase.status === "done"
                    ? "bg-emerald-500 border-emerald-500 text-white"
                    : phase.status === "running"
                      ? cn("border-2 animate-pulse", PHASE_COLORS[phase.id])
                      : phase.status === "failed"
                        ? "bg-red-500 border-red-500 text-white"
                        : "border-border text-muted-foreground"
                )}
              >
                {phase.status === "done" ? (
                  <Check className="w-3.5 h-3.5" />
                ) : phase.status === "running" ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : phase.status === "failed" ? (
                  <X className="w-3.5 h-3.5" />
                ) : (
                  <Circle className="w-3 h-3" />
                )}
              </div>
              {!isLast && (
                <div
                  className={cn(
                    "w-0.5 h-8 my-1",
                    phase.status === "done" ? "bg-emerald-500" : "bg-border"
                  )}
                />
              )}
            </div>

            {/* Content column */}
            <div className="flex-1 pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{meta?.icon}</span>
                  <span
                    className={cn(
                      "text-sm font-medium",
                      phase.status === "running"
                        ? "text-foreground"
                        : "text-muted-foreground"
                    )}
                  >
                    {phase.name}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    ({meta?.tool})
                  </span>
                </div>
                {phase.score !== null && (
                  <span
                    className={cn(
                      "text-xs font-mono font-bold",
                      phase.score >= 80
                        ? "text-emerald-400"
                        : phase.score >= 60
                          ? "text-amber-400"
                          : "text-red-400"
                    )}
                  >
                    {Math.round(phase.score)}%
                  </span>
                )}
              </div>

              {/* Progress bar for running phase */}
              {phase.status === "running" && (
                <Progress value={phase.progress} className="h-1 mt-1.5" />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
