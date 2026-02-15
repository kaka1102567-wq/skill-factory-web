"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Template, QualityTier } from "@/types/build";
import { StepTemplate } from "./step-template";
import { StepConfig } from "./step-config";
import { StepDataSources, type DataSourcesData } from "./step-data-sources";
import { StepUpload } from "./step-upload";
import { StepReview } from "./step-review";

const STEPS = ["Template", "Config", "Data Sources", "Upload", "Review"];

export function BuildWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);

  // Step 1 state
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);

  // Step 2 state
  const [config, setConfig] = useState({
    name: "",
    language: "vi",
    qualityTier: "standard" as QualityTier,
    platforms: ["claude"] as string[],
  });

  // Step 3 state (Data Sources)
  const [dataSources, setDataSources] = useState<DataSourcesData>({
    autoScrape: true,
    baselineUrls: [""],
  });

  // Step 4 state (Upload)
  const [files, setFiles] = useState<File[]>([]);
  const [urls, setUrls] = useState<string[]>([""]);
  const [githubRepo, setGithubRepo] = useState("");
  const [githubAnalyzeCode, setGithubAnalyzeCode] = useState(true);

  // Step 5 state
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Template selection auto-fills config
  const handleTemplateSelect = useCallback((tpl: Template) => {
    setSelectedTemplate(tpl);
    setConfig((prev) => ({
      ...prev,
      name: prev.name || tpl.name,
    }));
  }, []);

  // Step validation
  const canProceed = (): boolean => {
    switch (step) {
      case 0: return selectedTemplate !== null;
      case 1: return config.name.trim().length >= 3;
      case 2: return true; // Data Sources is always optional
      case 3: return files.length > 0 || urls.some((u) => u.trim().match(/^https?:\/\/.+/)) || githubRepo.trim().includes("github.com");
      case 4: return confirmed;
      default: return false;
    }
  };

  // Submit build
  const handleSubmit = async () => {
    if (!selectedTemplate) return;
    setSubmitting(true);
    setError(null);

    try {
      // Upload files if any
      let uploadedPaths: string[] = [];
      if (files.length > 0) {
        const formData = new FormData();
        files.forEach((f) => formData.append("files", f));
        const uploadRes = await fetch("/api/uploads", { method: "POST", body: formData });
        if (!uploadRes.ok) {
          const uploadErr = await uploadRes.json();
          throw new Error(uploadErr.error || "Upload failed");
        }
        const uploadData = await uploadRes.json();
        uploadedPaths = uploadData.files.map((f: { path: string }) => f.path);
      }

      // Separate input URLs (for content fetch) from baseline URLs
      const inputUrls = urls.filter((u) => u.trim().match(/^https?:\/\/.+/));

      // Create build
      const githubUrl = githubRepo.trim().includes("github.com") ? githubRepo.trim() : "";

      const body = {
        name: config.name,
        domain: selectedTemplate.domain,
        template_id: selectedTemplate.id,
        language: config.language,
        quality_tier: config.qualityTier,
        platforms: config.platforms,
        baseline_urls: dataSources.baselineUrls.filter((u) => u.trim()),
        input_urls: inputUrls,
        auto_scrape: dataSources.autoScrape,
        files: uploadedPaths,
        github_repo: githubUrl || undefined,
        github_analyze_code: githubAnalyzeCode,
      };

      const res = await fetch("/api/builds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Failed to create build");
      }

      const data = await res.json();
      router.push(`/build/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="flex items-center justify-center gap-1">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all",
                  i < step
                    ? "bg-emerald-500 border-emerald-500 text-white"
                    : i === step
                      ? "border-indigo-500 text-indigo-400 bg-indigo-500/10"
                      : "border-border text-muted-foreground",
                )}
              >
                {i < step ? "\u2713" : i + 1}
              </div>
              <span className={cn(
                "text-[10px] mt-1",
                i === step ? "text-indigo-400" : "text-muted-foreground",
              )}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={cn(
                "w-12 h-0.5 mx-1 mb-4",
                i < step ? "bg-emerald-500" : "bg-border",
              )} />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div className="min-h-[300px]">
        {step === 0 && (
          <StepTemplate
            selectedId={selectedTemplate?.id ?? null}
            onSelect={handleTemplateSelect}
          />
        )}
        {step === 1 && (
          <StepConfig
            config={config}
            onChange={(updates) => setConfig((prev) => ({ ...prev, ...updates }))}
          />
        )}
        {step === 2 && (
          <StepDataSources
            domain={selectedTemplate?.domain ?? "custom"}
            data={dataSources}
            onChange={(updates) => setDataSources((prev) => ({ ...prev, ...updates }))}
          />
        )}
        {step === 3 && (
          <StepUpload
            files={files}
            urls={urls}
            githubRepo={githubRepo}
            githubAnalyzeCode={githubAnalyzeCode}
            onFilesChange={setFiles}
            onUrlsChange={setUrls}
            onGithubRepoChange={setGithubRepo}
            onGithubAnalyzeCodeChange={setGithubAnalyzeCode}
          />
        )}
        {step === 4 && (
          <StepReview
            data={{
              name: config.name,
              domain: selectedTemplate?.domain ?? "custom",
              language: config.language,
              qualityTier: config.qualityTier,
              platforms: config.platforms,
              templateName: selectedTemplate?.name ?? null,
              fileCount: files.length,
              totalFileSize: files.reduce((s, f) => s + f.size, 0),
              urlCount: urls.filter((u) => u.trim()).length,
              autoScrape: dataSources.autoScrape,
              baselineUrlCount: dataSources.baselineUrls.filter((u) => u.trim()).length,
              githubRepo: githubRepo.trim().includes("github.com") ? githubRepo.trim() : undefined,
            }}
            confirmed={confirmed}
            onConfirmChange={setConfirmed}
            submitting={submitting}
            error={error}
          />
        )}
      </div>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between pt-4 border-t border-border">
        <Button
          variant="ghost"
          onClick={() => { setStep((s) => s - 1); setConfirmed(false); setError(null); }}
          disabled={step === 0}
          className="gap-1.5"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Button>

        {step < 4 ? (
          <Button
            onClick={() => setStep((s) => s + 1)}
            disabled={!canProceed()}
            className="gap-1.5"
          >
            Next
            <ArrowRight className="w-4 h-4" />
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={!canProceed() || submitting}
            className="gap-1.5"
          >
            <Rocket className="w-4 h-4" />
            {submitting ? "Creating build..." : "Start Build"}
          </Button>
        )}
      </div>
    </div>
  );
}
