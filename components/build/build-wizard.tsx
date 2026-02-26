"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Rocket, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Template } from "@/types/build";
import { StepTemplate } from "./step-template";
import { StepConfig } from "./step-config";
import { StepDataSources, type DataSourcesData } from "./step-data-sources";
import { StepUpload } from "./step-upload";
import { StepReview } from "./step-review";
import { useWizardState, clearWizardState, savePendingBuild } from "@/hooks/use-wizard-state";

const STEPS = ["Template", "Config", "Data Sources", "Upload", "Review"];

export function BuildWizard() {
  const router = useRouter();

  // Persisted wizard state (restored from sessionStorage on mount)
  const {
    step, setStep,
    selectedTemplate, setSelectedTemplate,
    config, setConfig,
    dataSources, setDataSources,
    urls, setUrls,
    githubRepo, setGithubRepo,
    githubAnalyzeCode, setGithubAnalyzeCode,
  } = useWizardState();

  // Transient UI state — not persisted
  const [files, setFiles] = useState<File[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<{
    current: number; total: number; currentFile: string;
    uploadedBytes: number; totalBytes: number; warnings: string[];
  } | null>(null);

  // Template selection auto-fills name if empty
  const handleTemplateSelect = useCallback((tpl: Template) => {
    setSelectedTemplate(tpl);
    setConfig((prev) => ({
      ...prev,
      name: prev.name || tpl.name,
    }));
  }, [setSelectedTemplate, setConfig]);

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

  type UploadOk = { ok: true; path: string; uploadDir: string };
  type UploadFail = { ok: false; reason: string };
  type UploadResult = UploadOk | UploadFail;

  const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB chunks
  const CHUNK_THRESHOLD = 8 * 1024 * 1024; // files >8MB use chunked upload

  // Small file upload (≤8MB) — single multipart POST via busboy
  const uploadSmallFile = async (
    file: File, uploadDir: string | null,
  ): Promise<UploadResult> => {
    const timeoutMs = 60_000; // 60s for small files

    for (let attempt = 0; attempt < 2; attempt++) {
      if (attempt > 0) await new Promise((r) => setTimeout(r, 2000));
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);

      try {
        const formData = new FormData();
        if (uploadDir) formData.append("upload_dir", uploadDir);
        formData.append("files", file);

        const res = await fetch("/api/uploads", {
          method: "POST", body: formData, signal: controller.signal,
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
          const reason = errData.error || `HTTP ${res.status}`;
          console.warn(`[Upload] ${file.name} attempt ${attempt + 1} failed: ${reason}`);
          if (attempt === 0) continue;
          return { ok: false, reason };
        }
        const data = await res.json();
        return { ok: true, path: data.files[0].path, uploadDir: data.upload_dir };
      } catch (err) {
        const reason = err instanceof DOMException && err.name === "AbortError"
          ? "timeout (>60s)" : err instanceof Error ? err.message : "network error";
        console.warn(`[Upload] ${file.name} attempt ${attempt + 1} error: ${reason}`);
        if (attempt === 0) continue;
        return { ok: false, reason };
      } finally { clearTimeout(timer); }
    }
    return { ok: false, reason: "unknown" };
  };

  // Large file upload (>8MB) — chunked binary POST, 5MB per chunk
  const uploadLargeFile = async (
    file: File, uploadDir: string | null,
  ): Promise<UploadResult> => {
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const chunkTimeoutMs = 60_000; // 60s per 5MB chunk
    let currentDir = uploadDir;

    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const end = Math.min(start + CHUNK_SIZE, file.size);
      const chunk = file.slice(start, end);
      let chunkOk = false;

      // Retry each chunk up to 2 times
      for (let attempt = 0; attempt < 2; attempt++) {
        if (attempt > 0) await new Promise((r) => setTimeout(r, 2000));
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), chunkTimeoutMs);

        try {
          const headers: Record<string, string> = {
            "Content-Type": "application/octet-stream",
            "X-File-Name": encodeURIComponent(file.name),
            "X-Chunk-Index": String(i),
            "X-Chunk-Total": String(totalChunks),
          };
          if (currentDir) headers["X-Upload-Dir"] = currentDir;

          const res = await fetch("/api/uploads/chunk", {
            method: "POST", body: chunk, signal: controller.signal, headers,
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
            console.warn(`[Upload] ${file.name} chunk ${i + 1}/${totalChunks} attempt ${attempt + 1}: ${errData.error}`);
            if (attempt === 0) continue;
            return { ok: false, reason: errData.error || `chunk ${i + 1} failed` };
          }

          const data = await res.json();
          if (!currentDir && data.upload_dir) currentDir = data.upload_dir;

          // Last chunk returns the final file info
          if (data.files) {
            return { ok: true, path: data.files[0].path, uploadDir: data.upload_dir };
          }
          chunkOk = true;
          break; // chunk succeeded, move to next
        } catch (err) {
          const reason = err instanceof DOMException && err.name === "AbortError"
            ? "chunk timeout" : err instanceof Error ? err.message : "network error";
          console.warn(`[Upload] ${file.name} chunk ${i + 1}/${totalChunks} attempt ${attempt + 1}: ${reason}`);
          if (attempt === 0) continue;
          return { ok: false, reason: `chunk ${i + 1}/${totalChunks} — ${reason}` };
        } finally { clearTimeout(timer); }
      }
      if (!chunkOk) return { ok: false, reason: `chunk ${i + 1}/${totalChunks} failed` };
    }
    return { ok: false, reason: "no final response from server" };
  };

  // Route to small or chunked upload based on file size
  const uploadSingleFile = (file: File, uploadDir: string | null): Promise<UploadResult> => {
    return file.size > CHUNK_THRESHOLD
      ? uploadLargeFile(file, uploadDir)
      : uploadSmallFile(file, uploadDir);
  };

  // Submit build — saves pending state before navigating away
  const handleSubmit = async () => {
    if (!selectedTemplate) return;
    setSubmitting(true);
    setError(null);
    setUploadProgress(null);

    try {
      // Upload files sequentially
      const uploadedPaths: string[] = [];
      if (files.length > 0) {
        const totalBytes = files.reduce((s, f) => s + f.size, 0);
        const warnings: string[] = [];
        let uploadDir: string | null = null;
        let uploadedBytes = 0;

        setUploadProgress({
          current: 0, total: files.length, currentFile: files[0].name,
          uploadedBytes: 0, totalBytes, warnings: [],
        });

        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          setUploadProgress({
            current: i, total: files.length, currentFile: file.name,
            uploadedBytes, totalBytes, warnings: [...warnings],
          });

          const result = await uploadSingleFile(file, uploadDir);
          if (result.ok) {
            uploadedPaths.push(result.path);
            if (!uploadDir) uploadDir = result.uploadDir;
            uploadedBytes += file.size;
          } else {
            warnings.push(`${file.name} (${result.reason})`);
            uploadedBytes += file.size;
          }
        }

        setUploadProgress({
          current: files.length, total: files.length, currentFile: "",
          uploadedBytes: totalBytes, totalBytes, warnings,
        });

        if (uploadedPaths.length === 0) {
          throw new Error("All file uploads failed");
        }
      }

      const inputUrls = urls.filter((u) => u.trim().match(/^https?:\/\/.+/));
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

      // Save pending build before API call — enables background recovery
      savePendingBuild("__creating__", "creating");

      const res = await fetch("/api/builds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errData = await res.json();
        clearWizardState();
        throw new Error(errData.error || "Failed to create build");
      }

      const data = await res.json();

      // Update pending build with real ID so navigation away can redirect back
      savePendingBuild(data.id, "creating");

      // Clear wizard state — build has been created successfully
      clearWizardState();

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

      {/* Upload progress indicator */}
      {submitting && uploadProgress && uploadProgress.total > 0 && (
        <div className="space-y-2 p-3 rounded-lg bg-muted/50 border border-border">
          <div className="flex items-center justify-between text-xs">
            <span className="text-foreground">
              {uploadProgress.current < uploadProgress.total
                ? <>Uploading <span className="font-medium">{uploadProgress.currentFile}</span>
                    {uploadProgress.currentFile && files[uploadProgress.current]?.size > 8 * 1024 * 1024 && (
                      <span className="text-muted-foreground ml-1">(chunked)</span>
                    )}
                  </>
                : "Upload complete"}
            </span>
            <span className="text-muted-foreground">
              {uploadProgress.current}/{uploadProgress.total} files
              {" "}({(uploadProgress.uploadedBytes / 1024 / 1024).toFixed(0)} / {(uploadProgress.totalBytes / 1024 / 1024).toFixed(0)} MB)
            </span>
          </div>
          <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full transition-all duration-300"
              style={{ width: `${Math.round((uploadProgress.uploadedBytes / uploadProgress.totalBytes) * 100)}%` }}
            />
          </div>
          {uploadProgress.warnings.length > 0 && (
            <div className="flex items-start gap-1.5 text-xs text-amber-400">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>Skipped: {uploadProgress.warnings.join(", ")}</span>
            </div>
          )}
        </div>
      )}

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
            {submitting
              ? uploadProgress && uploadProgress.current < uploadProgress.total
                ? `Uploading ${uploadProgress.current + 1}/${uploadProgress.total}...`
                : "Creating build..."
              : "Start Build"}
          </Button>
        )}
      </div>
    </div>
  );
}
