"use client";

import { useEffect, useState } from "react";
import { Database, Globe, Plus, Trash2, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export interface DataSourcesData {
  autoScrape: boolean;
  seekersOutputDir: string;
  baselineUrls: string[];
}

interface StepDataSourcesProps {
  domain: string;
  data: DataSourcesData;
  onChange: (updates: Partial<DataSourcesData>) => void;
}

export function StepDataSources({ domain, data, onChange }: StepDataSourcesProps) {
  const [baselineStatus, setBaselineStatus] = useState<"loading" | "found" | "none">("loading");

  useEffect(() => {
    if (!domain) { setBaselineStatus("none"); return; }
    fetch(`/api/baselines?domain=${encodeURIComponent(domain)}`)
      .then((r) => r.ok ? r.json() : [])
      .then((list: { seekers_output_dir?: string }[]) => {
        if (list.length > 0 && list[0].seekers_output_dir) {
          setBaselineStatus("found");
          if (!data.seekersOutputDir) {
            onChange({ seekersOutputDir: list[0].seekers_output_dir });
          }
        } else {
          setBaselineStatus("none");
        }
      })
      .catch(() => setBaselineStatus("none"));
  }, [domain]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateUrl = (i: number, value: string) => {
    const next = [...data.baselineUrls];
    next[i] = value;
    onChange({ baselineUrls: next });
  };
  const addUrl = () => onChange({ baselineUrls: [...data.baselineUrls, ""] });
  const removeUrl = (i: number) => onChange({ baselineUrls: data.baselineUrls.filter((_, idx) => idx !== i) });

  const validUrlCount = data.baselineUrls.filter((u) => u.trim()).length;

  return (
    <div className="space-y-6">
      {/* Baseline status */}
      <div className={cn(
        "p-4 rounded-xl border flex items-start gap-3",
        baselineStatus === "found"
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-amber-500/30 bg-amber-500/5",
      )}>
        {baselineStatus === "found" ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-400 mt-0.5 shrink-0" />
        ) : (
          <AlertCircle className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
        )}
        <div>
          <p className="text-sm font-medium text-foreground">
            {baselineStatus === "loading" && "Checking baseline..."}
            {baselineStatus === "found" && `Baseline found for "${domain}"`}
            {baselineStatus === "none" && `No baseline found for "${domain}"`}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {baselineStatus === "found"
              ? "The build will use the existing baseline. You can still add more data sources below."
              : "Enable auto-scrape to build a baseline before the pipeline runs."}
          </p>
        </div>
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
          <Database className={cn("w-5 h-5", data.autoScrape ? "text-indigo-400" : "text-muted-foreground")} />
          <div>
            <p className="text-sm font-medium text-foreground">
              {data.autoScrape ? "Auto-scrape enabled" : "Auto-scrape disabled"}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {data.autoScrape
                ? "skill-seekers will scrape documentation before the build starts"
                : "Build will use existing baseline or legacy scraping"}
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
                <button type="button" onClick={() => removeUrl(i)} className="text-muted-foreground hover:text-red-400">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}
          <Button type="button" variant="ghost" size="sm" onClick={addUrl} className="gap-1.5">
            <Plus className="w-3.5 h-3.5" /> Add URL
          </Button>
        </div>
      )}

      {/* Seekers output dir (advanced) */}
      <div className="space-y-2">
        <Label className="text-xs text-muted-foreground">Seekers Output Directory (optional)</Label>
        <Input
          value={data.seekersOutputDir}
          onChange={(e) => onChange({ seekersOutputDir: e.target.value })}
          placeholder="e.g. output/fb-ads-meta/"
          className="text-sm"
        />
        <p className="text-xs text-muted-foreground">
          Leave empty to auto-generate. Points to the directory containing SKILL.md + references.
        </p>
      </div>

      {/* Summary */}
      {(validUrlCount > 0 || data.seekersOutputDir) && (
        <div className="p-3 rounded-xl bg-muted/50 border border-border">
          <p className="text-xs text-muted-foreground">
            {data.autoScrape && validUrlCount > 0 && `${validUrlCount} URL(s) to scrape`}
            {data.autoScrape && validUrlCount > 0 && data.seekersOutputDir && " | "}
            {data.seekersOutputDir && `Output: ${data.seekersOutputDir}`}
          </p>
        </div>
      )}
    </div>
  );
}
