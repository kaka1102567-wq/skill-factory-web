"use client";

import { useState, useEffect } from "react";
import { FileText, BookOpen, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface SkillPreviewProps {
  buildId: string;
}

interface KnowledgeFile {
  name: string;
  content: string;
}

export function SkillPreview({ buildId }: SkillPreviewProps) {
  const [skillContent, setSkillContent] = useState<string | null>(null);
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);
  const [activeFile, setActiveFile] = useState("SKILL.md");
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [skillRes, knowledgeRes] = await Promise.all([
          fetch(`/api/builds/${buildId}?content=skill`),
          fetch(`/api/builds/${buildId}?content=knowledge`),
        ]);
        if (cancelled) return;
        const skillData = await skillRes.json();
        const knowledgeData = await knowledgeRes.json();
        if (skillData.content) setSkillContent(skillData.content);
        if (knowledgeData.files) setKnowledgeFiles(knowledgeData.files);
      } catch {
        // fetch failed
      }
      if (!cancelled) setLoading(false);
    }
    load();
    return () => { cancelled = true; };
  }, [buildId]);

  const currentContent =
    activeFile === "SKILL.md"
      ? skillContent
      : knowledgeFiles.find((f) => f.name === activeFile)?.content;

  const copyToClipboard = async () => {
    if (!currentContent) return;
    await navigator.clipboard.writeText(currentContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
        Loading preview...
      </div>
    );
  }

  if (!skillContent && knowledgeFiles.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground text-sm">
        No output files found.
      </div>
    );
  }

  return (
    <div className="flex gap-4 min-h-[500px]">
      {/* File tree sidebar */}
      <div className="w-52 shrink-0 rounded-xl bg-card border border-border overflow-auto">
        <div className="p-3 border-b border-border">
          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Output Files
          </h4>
        </div>
        <div className="p-2 space-y-0.5">
          {skillContent && (
            <button
              onClick={() => setActiveFile("SKILL.md")}
              className={cn(
                "w-full text-left px-2.5 py-1.5 rounded-lg text-sm flex items-center gap-2 transition-colors",
                activeFile === "SKILL.md"
                  ? "bg-indigo-500/15 text-indigo-400"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <FileText className="h-3.5 w-3.5 shrink-0" />
              SKILL.md
            </button>
          )}
          {knowledgeFiles.length > 0 && (
            <>
              <div className="px-2.5 py-1.5 text-[10px] text-muted-foreground font-semibold uppercase tracking-wider mt-2">
                knowledge/
              </div>
              {knowledgeFiles.map((f) => (
                <button
                  key={f.name}
                  onClick={() => setActiveFile(f.name)}
                  className={cn(
                    "w-full text-left px-2.5 py-1.5 rounded-lg text-sm flex items-center gap-2 pl-4 transition-colors",
                    activeFile === f.name
                      ? "bg-indigo-500/15 text-indigo-400"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <BookOpen className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{f.name.replace(".md", "")}</span>
                </button>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 rounded-xl border border-border overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card">
          <span className="text-sm font-medium text-foreground">{activeFile}</span>
          <button
            onClick={copyToClipboard}
            className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
            title="Copy to clipboard"
          >
            {copied ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Rendered markdown */}
        <div className="flex-1 overflow-auto p-5 bg-[oklch(0.10_0.01_260)]">
          {currentContent ? (
            <SimpleMarkdown content={currentContent} />
          ) : (
            <div className="text-muted-foreground text-center py-10">
              File not found
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Lightweight markdown renderer — no external deps */
function SimpleMarkdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeBuffer: string[] = [];
  let codeLang = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block toggle
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <pre key={`code-${i}`} className="my-3 p-3 rounded-lg bg-black/30 border border-border text-xs font-mono overflow-x-auto text-emerald-300">
            {codeBuffer.join("\n")}
          </pre>
        );
        codeBuffer = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
        codeLang = line.slice(3).trim();
      }
      continue;
    }

    if (inCodeBlock) {
      codeBuffer.push(line);
      continue;
    }

    // Headings
    if (line.startsWith("### ")) {
      elements.push(<h3 key={i} className="text-base font-semibold text-foreground mt-5 mb-2">{renderInline(line.slice(4))}</h3>);
    } else if (line.startsWith("## ")) {
      elements.push(<h2 key={i} className="text-lg font-bold text-foreground mt-6 mb-2 pb-1 border-b border-border">{renderInline(line.slice(3))}</h2>);
    } else if (line.startsWith("# ")) {
      elements.push(<h1 key={i} className="text-xl font-bold text-foreground mt-4 mb-3">{renderInline(line.slice(2))}</h1>);
    } else if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(<li key={i} className="ml-4 text-sm text-foreground/90 leading-relaxed list-disc">{renderInline(line.slice(2))}</li>);
    } else if (line.startsWith("---")) {
      elements.push(<hr key={i} className="my-4 border-border" />);
    } else if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
    } else {
      elements.push(<p key={i} className="text-sm text-foreground/90 leading-relaxed">{renderInline(line)}</p>);
    }
  }

  return <div>{elements}</div>;
}

function renderInline(text: string): React.ReactNode {
  // Split on **bold** and `code` patterns
  const parts = text.split(/(\*\*.*?\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i} className="px-1 py-0.5 rounded bg-muted text-xs font-mono text-indigo-300">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}
