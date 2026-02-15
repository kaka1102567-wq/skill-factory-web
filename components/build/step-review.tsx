"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import type { QualityTier } from "@/types/build";

const TIER_INFO: Record<QualityTier, { time: string; cost: string }> = {
  draft: { time: "~5 min", cost: "~$1" },
  standard: { time: "~15 min", cost: "~$5" },
  premium: { time: "~45 min", cost: "~$15" },
};

interface ReviewData {
  name: string;
  domain: string;
  language: string;
  qualityTier: QualityTier;
  platforms: string[];
  templateName: string | null;
  fileCount: number;
  totalFileSize: number;
  urlCount: number;
  autoScrape?: boolean;
  baselineUrlCount?: number;
  githubRepo?: string;
}

interface StepReviewProps {
  data: ReviewData;
  confirmed: boolean;
  onConfirmChange: (v: boolean) => void;
  submitting: boolean;
  error: string | null;
}

function useBaselineLabel(domain: string): string {
  const [label, setLabel] = useState("Checking...");
  useEffect(() => {
    if (!domain) { setLabel("None"); return; }
    fetch(`/api/baselines/${encodeURIComponent(domain)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data || data.status === "none") {
          setLabel("None (will auto-search during build)");
        } else if (data.status === "pending") {
          setLabel(`Pending — ${data.name || domain}`);
        } else {
          setLabel(`${data.refs_count} document(s) (${data.name || domain})`);
        }
      })
      .catch(() => setLabel("None"));
  }, [domain]);
  return label;
}

export function StepReview({ data, confirmed, onConfirmChange, submitting, error }: StepReviewProps) {
  const tier = TIER_INFO[data.qualityTier];
  const baselineLabel = useBaselineLabel(data.domain);

  const rows: [string, string][] = [
    ["Template", data.templateName || "\u2014"],
    ["Skill Name", data.name],
    ["Domain", data.domain],
    ["Language", data.language === "vi" ? "Tieng Viet" : "English"],
    ["Quality", `${data.qualityTier} (${tier.time}, ${tier.cost})`],
    ["Platforms", data.platforms.join(", ")],
    ["Baseline", baselineLabel],
    ["Auto-scrape", data.autoScrape ? `Yes (${data.baselineUrlCount || 0} URL(s))` : "No"],
    ["Files", data.fileCount > 0 ? `${data.fileCount} file(s) (${(data.totalFileSize / 1024 / 1024).toFixed(1)} MB)` : "\u2014"],
    ["URLs", data.urlCount > 0 ? `${data.urlCount} URL(s)` : "\u2014"],
    ["GitHub", data.githubRepo || "\u2014"],
  ];

  return (
    <div className="space-y-6">
      {/* Summary table */}
      <div className="rounded-xl border border-border overflow-hidden">
        {rows.map(([label, value], i) => (
          <div
            key={label}
            className={`flex items-center px-4 py-2.5 text-sm ${i % 2 === 0 ? "bg-card" : "bg-muted/30"}`}
          >
            <span className="w-32 text-muted-foreground shrink-0">{label}</span>
            <span className="text-foreground">{value}</span>
          </div>
        ))}
      </div>

      {/* Estimation */}
      <div className="p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/20">
        <p className="text-sm font-medium text-foreground mb-1">Estimation</p>
        <div className="flex gap-6 text-sm text-muted-foreground">
          <span>Time: {tier.time}</span>
          <span>Cost: {tier.cost}</span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Confirm checkbox */}
      <div className="flex items-center gap-3">
        <Checkbox
          id="confirm"
          checked={confirmed}
          onCheckedChange={(v) => onConfirmChange(v === true)}
          disabled={submitting}
        />
        <Label htmlFor="confirm" className="text-sm text-muted-foreground cursor-pointer">
          I have reviewed the configuration and am ready to start the build
        </Label>
      </div>

      {/* Submitting indicator */}
      {submitting && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          Creating build...
        </div>
      )}
    </div>
  );
}
