"use client";

import { useState, useEffect } from "react";
import { Loader2, Eye, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface RefDetail {
  filename: string;
  title: string;
  source_url: string;
  size_bytes: number;
  content: string;
}

interface BaselineDetail {
  domain: string;
  name: string;
  status: string;
  score: number;
  source: string;
  skill_md: string;
  topics: string[];
  references: RefDetail[];
  total_tokens: number;
}

type TabKey = "refs" | "topics" | "skillmd";

/** Expandable detail panel for a baseline — shows references, topics, and SKILL.md */
export function BaselineDetailPanel({ domain }: { domain: string }) {
  const [detail, setDetail] = useState<BaselineDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>("refs");
  const [previewRef, setPreviewRef] = useState<RefDetail | null>(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/baselines/${domain}/detail`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setDetail(data))
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [domain]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">Loading detail...</span>
      </div>
    );
  }

  if (!detail) {
    return <p className="text-sm text-muted-foreground py-4">No detail available</p>;
  }

  const tabs: { key: TabKey; label: string }[] = [
    { key: "refs", label: `References (${detail.references.length})` },
    { key: "topics", label: `Topics (${detail.topics.length})` },
    { key: "skillmd", label: "SKILL.md" },
  ];

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      <div className="flex gap-4 text-xs text-muted-foreground">
        <span>Score: <strong className="text-emerald-400">{Math.round(detail.score * 100)}%</strong></span>
        <span>Source: {detail.source}</span>
        <span>Tokens: {detail.total_tokens.toLocaleString()}</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted/50 rounded-lg p-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "px-3 py-1.5 rounded-md text-xs font-medium transition-colors",
              activeTab === tab.key
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "refs" && <ReferencesTab refs={detail.references} onPreview={setPreviewRef} />}
      {activeTab === "topics" && <TopicsTab topics={detail.topics} />}
      {activeTab === "skillmd" && <SkillMdTab content={detail.skill_md} />}

      {/* Preview modal */}
      {previewRef && <PreviewModal ref_detail={previewRef} onClose={() => setPreviewRef(null)} />}
    </div>
  );
}

/** List of reference documents with preview buttons */
function ReferencesTab({ refs, onPreview }: { refs: RefDetail[]; onPreview: (r: RefDetail) => void }) {
  return (
    <div className="space-y-2 max-h-80 overflow-y-auto">
      {refs.map((ref, i) => {
        let hostname = "";
        try { hostname = new URL(ref.source_url).hostname; } catch { /* no url */ }

        return (
          <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">{ref.title}</p>
              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                <span>{ref.filename}</span>
                <span>{(ref.size_bytes / 1024).toFixed(1)} KB</span>
                {hostname && (
                  <a
                    href={ref.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-indigo-400 hover:underline truncate max-w-[200px]"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {hostname}
                  </a>
                )}
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={() => onPreview(ref)} className="text-xs gap-1 shrink-0">
              <Eye className="w-3 h-3" /> Preview
            </Button>
          </div>
        );
      })}
    </div>
  );
}

/** Grid of topic badges */
function TopicsTab({ topics }: { topics: string[] }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {topics.map((topic, i) => (
        <div key={i} className="px-3 py-2 rounded-lg bg-muted/30 text-sm text-foreground">
          {topic}
        </div>
      ))}
    </div>
  );
}

/** Preformatted SKILL.md content */
function SkillMdTab({ content }: { content: string }) {
  return (
    <div className="max-h-96 overflow-y-auto">
      <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 p-4 rounded-lg">
        {content}
      </pre>
    </div>
  );
}

/** Full-screen modal to preview a reference document's markdown content */
function PreviewModal({ ref_detail, onClose }: { ref_detail: RefDetail; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-2xl max-h-[80vh] bg-card border border-border rounded-xl shadow-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div>
            <h3 className="text-sm font-semibold text-foreground">{ref_detail.title}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{ref_detail.filename}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <pre className="text-sm text-foreground whitespace-pre-wrap font-mono">
            {ref_detail.content}
          </pre>
        </div>
      </div>
    </div>
  );
}
