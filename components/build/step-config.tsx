"use client";

import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { QualityTier } from "@/types/build";

interface ConfigData {
  name: string;
  language: string;
  qualityTier: QualityTier;
  platforms: string[];
}

interface StepConfigProps {
  config: ConfigData;
  onChange: (updates: Partial<ConfigData>) => void;
}

const QUALITY_TIERS: { value: QualityTier; label: string; desc: string; time: string; cost: string }[] = [
  { value: "draft", label: "Draft", desc: "Fast, lower quality", time: "~5 min", cost: "~$1" },
  { value: "standard", label: "Standard", desc: "Balanced quality & speed", time: "~15 min", cost: "~$5" },
  { value: "premium", label: "Premium", desc: "Highest quality, thorough", time: "~45 min", cost: "~$15" },
];

const PLATFORM_OPTIONS = [
  { value: "claude", label: "Claude" },
  { value: "gemini", label: "Gemini" },
  { value: "openai", label: "OpenAI" },
  { value: "markdown", label: "Markdown" },
];

export function StepConfig({ config, onChange }: StepConfigProps) {
  const togglePlatform = (p: string) => {
    const next = config.platforms.includes(p)
      ? config.platforms.filter((x) => x !== p)
      : [...config.platforms, p];
    // At least 1 platform required
    if (next.length > 0) onChange({ platforms: next });
  };

  return (
    <div className="space-y-6">
      {/* Skill name */}
      <div className="space-y-2">
        <Label htmlFor="skill-name">Skill Name</Label>
        <Input
          id="skill-name"
          value={config.name}
          onChange={(e) => onChange({ name: e.target.value })}
          placeholder="e.g. Facebook Ads Vietnam 2025"
        />
        <p className="text-xs text-muted-foreground">At least 3 characters</p>
      </div>

      {/* Language */}
      <div className="space-y-2">
        <Label>Language</Label>
        <div className="flex gap-2">
          {[
            { value: "vi", label: "Tieng Viet" },
            { value: "en", label: "English" },
          ].map((lang) => (
            <button
              key={lang.value}
              type="button"
              onClick={() => onChange({ language: lang.value })}
              className={cn(
                "px-4 py-2 rounded-lg border text-sm transition-all",
                config.language === lang.value
                  ? "border-indigo-500 bg-indigo-500/10 text-indigo-400"
                  : "border-border bg-card text-muted-foreground hover:border-indigo-500/50",
              )}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </div>

      {/* Quality tier */}
      <div className="space-y-2">
        <Label>Quality Tier</Label>
        <div className="grid grid-cols-3 gap-3">
          {QUALITY_TIERS.map((tier) => (
            <button
              key={tier.value}
              type="button"
              onClick={() => onChange({ qualityTier: tier.value })}
              className={cn(
                "p-3 rounded-xl border text-left transition-all",
                config.qualityTier === tier.value
                  ? "border-indigo-500 bg-indigo-500/10"
                  : "border-border bg-card hover:border-indigo-500/50",
              )}
            >
              <p className="text-sm font-semibold text-foreground">{tier.label}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{tier.desc}</p>
              <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
                <span>{tier.time}</span>
                <span>{tier.cost}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Platforms */}
      <div className="space-y-2">
        <Label>Platforms</Label>
        <div className="flex flex-wrap gap-2">
          {PLATFORM_OPTIONS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => togglePlatform(p.value)}
              className={cn(
                "px-3 py-1.5 rounded-full border text-xs transition-all",
                config.platforms.includes(p.value)
                  ? "border-indigo-500 bg-indigo-500/10 text-indigo-400"
                  : "border-border text-muted-foreground hover:border-indigo-500/50",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Estimation bar */}
      <div className="p-3 rounded-xl bg-muted/50 border border-border">
        <p className="text-xs text-muted-foreground mb-1">Estimated</p>
        <div className="flex gap-4 text-sm text-foreground">
          <span>{QUALITY_TIERS.find((t) => t.value === config.qualityTier)?.time}</span>
          <span>{QUALITY_TIERS.find((t) => t.value === config.qualityTier)?.cost}</span>
        </div>
      </div>
    </div>
  );
}
