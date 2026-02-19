"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { PhaseId, BuildStatus } from "@/types/build";

export interface LogEntry {
  level: string;
  phase: string | null;
  message: string;
  timestamp: string;
}

export interface PhaseState {
  id: PhaseId;
  status: "done" | "running" | "pending" | "failed";
  progress: number;
  score: number | null;
  name: string;
}

export interface CostState {
  total_cost: number;
  total_tokens: number;
}

export interface PreStep {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "failed";
}

export interface BuildStreamState {
  status: BuildStatus;
  current_phase: PhaseId | null;
  phase_progress: number;
  quality_score: number | null;
  package_path: string | null;
  completed_at: string | null;
  review_status: "none" | "pending" | "completed";
}

const INITIAL_PHASES: PhaseState[] = [
  { id: "p0", status: "pending", progress: 0, score: null, name: "Baseline" },
  { id: "p1", status: "pending", progress: 0, score: null, name: "Audit" },
  { id: "p2", status: "pending", progress: 0, score: null, name: "Extract" },
  { id: "p3", status: "pending", progress: 0, score: null, name: "Deduplicate" },
  { id: "p4", status: "pending", progress: 0, score: null, name: "Verify" },
  { id: "p5", status: "pending", progress: 0, score: null, name: "Architect" },
];

export function useBuildStream(buildId: string) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [phases, setPhases] = useState<PhaseState[]>(INITIAL_PHASES);
  const [buildState, setBuildState] = useState<BuildStreamState | null>(null);
  const [cost, setCost] = useState<CostState>({ total_cost: 0, total_tokens: 0 });
  const [preSteps, setPreSteps] = useState<PreStep[]>([]);
  const [connected, setConnected] = useState(false);
  const [finished, setFinished] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(`/api/builds/${buildId}/logs`);
    eventSourceRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    // Initial state
    es.addEventListener("state", (e) => {
      const data = JSON.parse(e.data);
      setBuildState(data);

      // Reconstruct phase states from initial state
      if (data.current_phase) {
        const currentIdx = parseInt(data.current_phase.replace("p", ""));
        setPhases((prev) =>
          prev.map((p, i) => {
            if (i < currentIdx) return { ...p, status: "done", progress: 100 };
            if (i === currentIdx)
              return { ...p, status: "running", progress: data.phase_progress || 0 };
            return p;
          })
        );
      }
    });

    // Log events
    es.addEventListener("log", (e) => {
      const data = JSON.parse(e.data);
      setLogs((prev) => [...prev, data]);
    });

    // Phase updates
    es.addEventListener("phase", (e) => {
      const data = JSON.parse(e.data);
      setPhases((prev) =>
        prev.map((p) => {
          if (p.id === data.phase) {
            return {
              ...p,
              status: data.status === "done" ? "done" : "running",
              progress: data.progress || 0,
              name: data.name || p.name,
            };
          }
          // Mark previous phases as done
          const phaseIdx = parseInt(data.phase.replace("p", ""));
          const thisIdx = parseInt(p.id.replace("p", ""));
          if (thisIdx < phaseIdx && p.status !== "done") {
            return { ...p, status: "done", progress: 100 };
          }
          return p;
        })
      );
      setBuildState((prev) =>
        prev
          ? { ...prev, current_phase: data.phase, phase_progress: data.progress || 0 }
          : prev
      );
    });

    // Quality gate results
    es.addEventListener("quality", (e) => {
      const data = JSON.parse(e.data);
      if (data.phase) {
        setPhases((prev) =>
          prev.map((p) => (p.id === data.phase ? { ...p, score: data.score } : p))
        );
      }
      if (data.quality_score) {
        setBuildState((prev) =>
          prev ? { ...prev, quality_score: data.quality_score } : prev
        );
      }
    });

    // Cost tracking
    es.addEventListener("cost", (e) => {
      const data = JSON.parse(e.data);
      setCost({
        total_cost: data.api_cost_usd ?? 0,
        total_tokens: data.tokens_used ?? 0,
      });
    });

    // Pre-processing / discovery steps
    es.addEventListener("pre-step", (e) => {
      const data = JSON.parse(e.data) as PreStep;
      setPreSteps((prev) => {
        const idx = prev.findIndex((s) => s.id === data.id);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = { ...next[idx], ...data };
          return next;
        }
        return [...prev, data];
      });
    });

    // Conflict (pauses build)
    es.addEventListener("conflict", () => {
      setBuildState((prev) =>
        prev ? { ...prev, status: "paused", review_status: "pending" } : prev
      );
    });

    // Build complete
    es.addEventListener("complete", (e) => {
      const data = JSON.parse(e.data);
      setBuildState((prev) =>
        prev
          ? {
              ...prev,
              status: data.status,
              quality_score: data.quality_score || prev.quality_score,
              package_path: data.package_path,
              completed_at: data.completed_at,
            }
          : prev
      );

      // Mark all phases done on success
      if (data.status === "completed") {
        setPhases((prev) => prev.map((p) => ({ ...p, status: "done", progress: 100 })));
      }

      setFinished(true);
      es.close();
    });

    return es;
  }, [buildId]);

  useEffect(() => {
    const es = connect();
    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [connect]);

  return { logs, phases, preSteps, buildState, cost, connected, finished };
}
