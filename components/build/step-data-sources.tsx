"use client";

import { useEffect, useState } from "react";
import {
  Database,
  Globe,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface DataSourcesData {
  autoScrape: boolean;
  baselineUrls: string[];
}

interface BaselineApiResponse {
  status: "ready" | "pending" | "none";
  domain: string;
  name: string;
  refs_count: number;
  source: string;
  message?: string;
}

interface StepDataSourcesProps {
  domain: string;
  data: DataSourcesData;
  onChange: (updates: Partial<DataSourcesData>) => void;
}

function BaselineStatus({ domain }: { domain: string }) {
  const [baseline, setBaseline] = useState<BaselineApiResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!domain) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetch(`/api/baselines/${encodeURIComponent(domain)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        setBaseline(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [domain]);

  if (loading) {
    return (
      <div className="rounded-xl border border-border p-4 flex items-center gap-3">
        <Loader2 className="w-5 h-5 text-muted-foreground animate-spin shrink-0" />
        <p className="text-sm text-muted-foreground">
          Checking reference documents...
        </p>
      </div>
    );
  }

  if (!baseline || baseline.status === "none") {
    return (
      <div className="rounded-xl border border-zinc-700 p-4">
        <div className="flex items-center gap-2 text-zinc-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="text-sm font-medium">
            No reference documents for this domain
          </span>
        </div>
        <p className="text-xs text-zinc-500 mt-1 ml-6">
          AI will only use the transcripts/URLs/PDFs you provide
        </p>
      </div>
    );
  }

  if (baseline.status === "pending") {
    return (
      <div className="rounded-xl border border-amber-800 bg-amber-950/30 p-4">
        <div className="flex items-center gap-2 text-amber-400">
          <Clock className="h-4 w-4 shrink-0" />
          <span className="text-sm font-medium">
            Reference documents will be auto-scraped during build
          </span>
        </div>
        <p className="text-xs text-zinc-500 mt-1 ml-6">
          The system will find authoritative docs about{" "}
          <span className="text-zinc-400">{baseline.name}</span> before starting
        </p>
      </div>
    );
  }

  // status === "ready"
  return (
    <div className="rounded-xl border border-emerald-800 bg-emerald-950/30 p-4">
      <div className="flex items-center gap-2 text-emerald-400">
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        <span className="text-sm font-medium">
          {baseline.refs_count} reference document
          {baseline.refs_count !== 1 ? "s" : ""} ready
        </span>
      </div>
      {baseline.source && (
        <p className="text-xs text-zinc-500 mt-1 ml-6">
          Source: {baseline.source}
        </p>
      )}
    </div>
  );
}

export function StepDataSources({
  domain,
  data,
  onChange,
}: StepDataSourcesProps) {
  const updateUrl = (i: number, value: string) => {
    const next = [...data.baselineUrls];
    next[i] = value;
    onChange({ baselineUrls: next });
  };
  const addUrl = () =>
    onChange({ baselineUrls: [...data.baselineUrls, ""] });
  const removeUrl = (i: number) =>
    onChange({
      baselineUrls: data.baselineUrls.filter((_, idx) => idx !== i),
    });

  const validUrlCount = data.baselineUrls.filter((u) => u.trim()).length;

  return (
    <div className="space-y-6">
      {/* Auto-detect baseline status */}
      <div className="space-y-2">
        <Label className="flex items-center gap-1.5">
          Reference Documents (Baseline)
        </Label>
        <BaselineStatus domain={domain} />
        <p className="text-xs text-muted-foreground">
          The system automatically uses these documents to verify the accuracy of
          extracted knowledge.
        </p>
      </div>

      {/* Auto-scrape toggle */}
      <div className="space-y-2">
        <Label>Auto-scrape Baseline</Label>
        <button
          type="button"
          onClick={() => onChange({ autoScrape: !data.autoScrape })}
          className={cn(
            "w-full p-4 rounded-xl border text-left transition-all flex items-center gap-3",
            data.autoScrape
              ? "border-indigo-500 bg-indigo-500/10"
              : "border-border bg-card hover:border-indigo-500/50",
          )}
        >
          <Database
            className={cn(
              "w-5 h-5",
              data.autoScrape ? "text-indigo-400" : "text-muted-foreground",
            )}
          />
          <div>
            <p className="text-sm font-medium text-foreground">
              {data.autoScrape ? "Auto-scrape enabled" : "Auto-scrape disabled"}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {data.autoScrape
                ? "skill-seekers will scrape documentation before the build starts"
                : "Build will use existing baseline only"}
            </p>
          </div>
        </button>
      </div>

      {/* Baseline URLs */}
      {data.autoScrape && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-muted-foreground" />
            <Label>Documentation URLs</Label>
          </div>
          {data.baselineUrls.map((url, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input
                value={url}
                onChange={(e) => updateUrl(i, e.target.value)}
                placeholder="https://developers.facebook.com/docs/..."
                className="flex-1"
              />
              {data.baselineUrls.length > 1 && (
                <button
                  type="button"
                  onClick={() => removeUrl(i)}
                  className="text-muted-foreground hover:text-red-400"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={addUrl}
            className="gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" /> Add URL
          </Button>
        </div>
      )}

      {/* Summary */}
      {data.autoScrape && validUrlCount > 0 && (
        <div className="p-3 rounded-xl bg-muted/50 border border-border">
          <p className="text-xs text-muted-foreground">
            {validUrlCount} URL(s) to scrape
          </p>
        </div>
      )}
    </div>
  );
}
