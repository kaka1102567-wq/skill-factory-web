export type BuildStatus = "pending" | "queued" | "running" | "paused" | "completed" | "failed";
export type PhaseId = "p0" | "p1" | "p2" | "p3" | "p4" | "p5";
export type QualityTier = "draft" | "standard" | "premium";
export type LogLevel = "debug" | "info" | "warn" | "error" | "phase";

export interface Build {
  id: string;
  name: string;
  domain: string | null;
  status: BuildStatus;
  current_phase: PhaseId | null;
  phase_progress: number;
  config_yaml: string;
  template_id: string | null;
  quality_score: number | null;
  atoms_extracted: number | null;
  atoms_deduplicated: number | null;
  atoms_verified: number | null;
  compression_ratio: number | null;
  api_cost_usd: number;
  tokens_used: number;
  output_path: string | null;
  package_path: string | null;
  created_by: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  review_status: "none" | "pending" | "completed";
  review_data: string | null;
}

export interface BuildLog {
  id: number;
  build_id: string;
  timestamp: string;
  level: LogLevel;
  phase: PhaseId | null;
  message: string;
  metadata: string | null;
}

export interface Template {
  id: string;
  name: string;
  domain: string;
  description: string | null;
  icon: string;
  config_yaml: string;
  is_default: number;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface DashboardStats {
  total_builds: number;
  completed_builds: number;
  avg_quality: number | null;
  total_atoms: number;
  total_cost: number;
  running_builds: number;
}

export interface PhaseInfo {
  id: PhaseId;
  name: string;
  icon: string;
  tool: string;
  status: "done" | "running" | "pending" | "failed" | "skipped";
  score: number | null;
  progress: number;
}

export const PHASES: Omit<PhaseInfo, "status" | "score" | "progress">[] = [
  { id: "p0", name: "Baseline", icon: "📖", tool: "Seekers" },
  { id: "p1", name: "Audit", icon: "🔍", tool: "Claude" },
  { id: "p2", name: "Extract", icon: "⚛️", tool: "Claude" },
  { id: "p3", name: "Deduplicate", icon: "🔄", tool: "Claude+Seekers" },
  { id: "p4", name: "Verify", icon: "✅", tool: "Seekers+Claude" },
  { id: "p5", name: "Architect", icon: "📦", tool: "Claude+Seekers" },
];
