"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { Template, QualityTier } from "@/types/build";
import type { DataSourcesData } from "@/components/build/step-data-sources";

const WIZARD_STATE_KEY = "wizard_state";
const PENDING_BUILD_KEY = "pending_build";

export interface WizardConfig {
  name: string;
  language: string;
  qualityTier: QualityTier;
  platforms: string[];
}

interface PersistedWizardState {
  step: number;
  selectedTemplate: Template | null;
  config: WizardConfig;
  dataSources: DataSourcesData;
  urls: string[];
  githubRepo: string;
  githubAnalyzeCode: boolean;
}

interface PendingBuild {
  buildId: string;
  status: "creating" | "uploading";
}

const DEFAULT_CONFIG: WizardConfig = {
  name: "",
  language: "vi",
  qualityTier: "standard",
  platforms: ["claude"],
};

const DEFAULT_DATA_SOURCES: DataSourcesData = {
  autoScrape: true,
  baselineUrls: [""],
};

function loadWizardState(): PersistedWizardState | null {
  try {
    const raw = sessionStorage.getItem(WIZARD_STATE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedWizardState;
  } catch {
    return null;
  }
}

function saveWizardState(state: PersistedWizardState): void {
  try {
    sessionStorage.setItem(WIZARD_STATE_KEY, JSON.stringify(state));
  } catch {
    // sessionStorage unavailable (SSR or quota exceeded) — silently ignore
  }
}

export function clearWizardState(): void {
  try {
    sessionStorage.removeItem(WIZARD_STATE_KEY);
    sessionStorage.removeItem(PENDING_BUILD_KEY);
  } catch { /* ignore */ }
}

export function savePendingBuild(buildId: string, status: PendingBuild["status"]): void {
  try {
    sessionStorage.setItem(PENDING_BUILD_KEY, JSON.stringify({ buildId, status }));
  } catch { /* ignore */ }
}

export function useWizardState() {
  const router = useRouter();

  // Initialize from sessionStorage on first render (client-side only)
  const [initialized, setInitialized] = useState(false);
  const [step, setStepRaw] = useState(0);
  const [selectedTemplate, setSelectedTemplateRaw] = useState<Template | null>(null);
  const [config, setConfigRaw] = useState<WizardConfig>(DEFAULT_CONFIG);
  const [dataSources, setDataSourcesRaw] = useState<DataSourcesData>(DEFAULT_DATA_SOURCES);
  const [urls, setUrlsRaw] = useState<string[]>([""]);
  const [githubRepo, setGithubRepoRaw] = useState("");
  const [githubAnalyzeCode, setGithubAnalyzeCodeRaw] = useState(true);

  // On mount: check for pending build first, then restore wizard state
  useEffect(() => {
    // Check for a pending build in progress
    try {
      const raw = sessionStorage.getItem(PENDING_BUILD_KEY);
      if (raw) {
        const pending = JSON.parse(raw) as PendingBuild;
        if (pending.buildId) {
          // Verify build exists via API, then redirect
          fetch(`/api/builds/${pending.buildId}`)
            .then((res) => {
              if (res.ok) {
                router.replace(`/build/${pending.buildId}`);
              } else {
                // Build not found — clear stale pending state
                sessionStorage.removeItem(PENDING_BUILD_KEY);
              }
            })
            .catch(() => {
              sessionStorage.removeItem(PENDING_BUILD_KEY);
            });
          return; // Don't restore wizard state if redirecting
        }
      }
    } catch { /* ignore */ }

    // Restore wizard state from sessionStorage
    const saved = loadWizardState();
    if (saved) {
      setStepRaw(saved.step ?? 0);
      setSelectedTemplateRaw(saved.selectedTemplate ?? null);
      setConfigRaw(saved.config ?? DEFAULT_CONFIG);
      setDataSourcesRaw(saved.dataSources ?? DEFAULT_DATA_SOURCES);
      setUrlsRaw(saved.urls ?? [""]);
      setGithubRepoRaw(saved.githubRepo ?? "");
      setGithubAnalyzeCodeRaw(saved.githubAnalyzeCode ?? true);
    }

    setInitialized(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist to sessionStorage whenever state changes (after initialization)
  useEffect(() => {
    if (!initialized) return;
    saveWizardState({
      step,
      selectedTemplate,
      config,
      dataSources,
      urls,
      githubRepo,
      githubAnalyzeCode,
    });
  }, [initialized, step, selectedTemplate, config, dataSources, urls, githubRepo, githubAnalyzeCode]);

  const setStep = useCallback((updater: number | ((prev: number) => number)) => {
    setStepRaw(updater);
  }, []);

  const setSelectedTemplate = useCallback((tpl: Template | null) => {
    setSelectedTemplateRaw(tpl);
  }, []);

  const setConfig = useCallback((updater: WizardConfig | ((prev: WizardConfig) => WizardConfig)) => {
    setConfigRaw(updater);
  }, []);

  const setDataSources = useCallback((updater: DataSourcesData | ((prev: DataSourcesData) => DataSourcesData)) => {
    setDataSourcesRaw(updater);
  }, []);

  const setUrls = useCallback((updater: string[] | ((prev: string[]) => string[])) => {
    setUrlsRaw(updater);
  }, []);

  const setGithubRepo = useCallback((v: string) => {
    setGithubRepoRaw(v);
  }, []);

  const setGithubAnalyzeCode = useCallback((v: boolean) => {
    setGithubAnalyzeCodeRaw(v);
  }, []);

  return {
    step, setStep,
    selectedTemplate, setSelectedTemplate,
    config, setConfig,
    dataSources, setDataSources,
    urls, setUrls,
    githubRepo, setGithubRepo,
    githubAnalyzeCode, setGithubAnalyzeCode,
  };
}
