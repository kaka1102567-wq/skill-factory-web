"use client";

import { useRef, useEffect, useState } from "react";
import { Terminal, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LogEntry } from "@/hooks/use-build-stream";

const LEVEL_COLORS: Record<string, string> = {
  debug: "text-gray-500",
  info: "text-gray-300",
  warn: "text-amber-400",
  error: "text-red-400",
  phase: "text-indigo-400",
};

export function LogViewer({ logs }: { logs: LogEntry[] }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Detect manual scroll
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  const filteredLogs =
    filter === "all" ? logs : logs.filter((l) => l.level === filter);

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString("vi-VN", { hour12: false });
    } catch {
      return "";
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-card">
        <div className="flex items-center gap-2">
          <Terminal className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-xs font-semibold text-muted-foreground">
            Build Logs
          </span>
          <span className="text-xs text-muted-foreground">({logs.length})</span>
        </div>
        <div className="flex items-center gap-1">
          {["all", "info", "warn", "error"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-2 py-0.5 rounded text-xs transition-colors",
                filter === f
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Log content */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-3 font-mono text-xs leading-relaxed bg-[oklch(0.08_0.01_260)] min-h-[300px] max-h-[500px]"
      >
        {filteredLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <span>Waiting for logs...</span>
          </div>
        ) : (
          filteredLogs.map((log, i) => (
            <div key={i} className="flex items-start gap-2 py-0.5 hover:bg-white/5">
              <span className="text-muted-foreground shrink-0 w-16">
                {formatTime(log.timestamp)}
              </span>
              {log.phase && (
                <span className="text-indigo-400 shrink-0 px-1 rounded bg-white/5">
                  [{log.phase.toUpperCase()}]
                </span>
              )}
              <span
                className={cn(
                  "min-w-0 break-words",
                  LEVEL_COLORS[log.level] || "text-gray-300"
                )}
              >
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Scroll-to-bottom button */}
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true);
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          }}
          className="flex items-center justify-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs absolute bottom-4 right-4 rounded-full shadow-lg hover:bg-indigo-700 transition-colors"
        >
          <ArrowDown className="w-3 h-3" />
          Scroll to bottom
        </button>
      )}
    </div>
  );
}
