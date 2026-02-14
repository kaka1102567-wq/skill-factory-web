import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { BuildStatus, PhaseId } from "@/types/build";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCost(usd: number): string {
  return `${usd.toFixed(2)}`;
}

export function formatNumber(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
}

export function formatDuration(start: string | null, end: string | null): string {
  if (!start) return "—";
  const startDate = new Date(start);
  const endDate = end ? new Date(end) : new Date();
  const diffMs = endDate.getTime() - startDate.getTime();
  const mins = Math.floor(diffMs / 60000);
  const secs = Math.floor((diffMs % 60000) / 1000);
  if (mins > 60) {
    const hrs = Math.floor(mins / 60);
    return `${hrs}h ${mins % 60}m`;
  }
  return `${mins}m ${secs}s`;
}

export function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  const hours = Math.floor(mins / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) return `${days} ngày trước`;
  if (hours > 0) return `${hours} giờ trước`;
  if (mins > 0) return `${mins} phút trước`;
  return "vừa xong";
}

export function getStatusColor(status: BuildStatus): string {
  const colors: Record<BuildStatus, string> = {
    completed: "text-emerald-400",
    running: "text-blue-400",
    queued: "text-gray-400",
    pending: "text-gray-500",
    paused: "text-yellow-400",
    failed: "text-red-400",
  };
  return colors[status];
}

export function getStatusBgColor(status: BuildStatus): string {
  const colors: Record<BuildStatus, string> = {
    completed: "bg-emerald-400/10 text-emerald-400 border-emerald-400/20",
    running: "bg-blue-400/10 text-blue-400 border-blue-400/20",
    queued: "bg-gray-400/10 text-gray-400 border-gray-400/20",
    pending: "bg-gray-500/10 text-gray-500 border-gray-500/20",
    paused: "bg-yellow-400/10 text-yellow-400 border-yellow-400/20",
    failed: "bg-red-400/10 text-red-400 border-red-400/20",
  };
  return colors[status];
}

export function getStatusLabel(status: BuildStatus): string {
  const labels: Record<BuildStatus, string> = {
    completed: "Hoàn thành",
    running: "Đang chạy",
    queued: "Chờ xử lý",
    pending: "Đang tạo",
    paused: "Tạm dừng",
    failed: "Thất bại",
  };
  return labels[status];
}

export function getPhaseLabel(phase: PhaseId): string {
  const labels: Record<PhaseId, string> = {
    p0: "Baseline",
    p1: "Audit",
    p2: "Extract",
    p3: "Deduplicate",
    p4: "Verify",
    p5: "Architect",
  };
  return labels[phase];
}

export function getOverallProgress(currentPhase: PhaseId | null, phaseProgress: number): number {
  if (!currentPhase) return 0;
  const phaseIndex = parseInt(currentPhase.replace("p", ""));
  const phaseWeight = 100 / 6;
  return Math.round(phaseIndex * phaseWeight + (phaseProgress / 100) * phaseWeight);
}
