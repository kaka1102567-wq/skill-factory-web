"use client";

import { useCallback, useRef, useState } from "react";
import { FileText, Link2, Plus, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const ALLOWED_EXTENSIONS = [".txt", ".md", ".pdf", ".json", ".yaml", ".yml", ".csv"];

interface StepUploadProps {
  files: File[];
  urls: string[];
  onFilesChange: (files: File[]) => void;
  onUrlsChange: (urls: string[]) => void;
}

export function StepUpload({ files, urls, onFilesChange, onUrlsChange }: StepUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const addFiles = useCallback(
    (newFiles: FileList | File[]) => {
      const valid = Array.from(newFiles).filter((f) => {
        const ext = "." + f.name.split(".").pop()?.toLowerCase();
        return ALLOWED_EXTENSIONS.includes(ext) && f.size <= 50 * 1024 * 1024;
      });
      onFilesChange([...files, ...valid]);
    },
    [files, onFilesChange],
  );

  const removeFile = (index: number) => {
    onFilesChange(files.filter((_, i) => i !== index));
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length > 0) addFiles(e.dataTransfer.files);
    },
    [addFiles],
  );

  const updateUrl = (index: number, value: string) => {
    const next = [...urls];
    next[index] = value;
    onUrlsChange(next);
  };

  const addUrl = () => onUrlsChange([...urls, ""]);
  const removeUrl = (index: number) => onUrlsChange(urls.filter((_, i) => i !== index));

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const validUrlCount = urls.filter((u) => u.trim()).length;

  return (
    <div className="space-y-6">
      {/* Drag-drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex flex-col items-center justify-center gap-3 p-8 rounded-xl border-2 border-dashed cursor-pointer transition-all",
          dragOver
            ? "border-indigo-500 bg-indigo-500/10"
            : "border-border hover:border-indigo-500/50 hover:bg-muted/30",
        )}
      >
        <Upload className="w-8 h-8 text-muted-foreground" />
        <div className="text-center">
          <p className="text-sm text-foreground font-medium">
            Drop files here or click to browse
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {ALLOWED_EXTENSIONS.join(", ")} — max 50MB/file
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ALLOWED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((file, i) => (
            <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-card border border-border">
              <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="text-sm text-foreground truncate flex-1">{file.name}</span>
              <span className="text-xs text-muted-foreground">
                {(file.size / 1024).toFixed(0)} KB
              </span>
              <button type="button" onClick={() => removeFile(i)} className="text-muted-foreground hover:text-red-400">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* URL inputs */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Link2 className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Baseline URLs</span>
        </div>
        {urls.map((url, i) => (
          <div key={i} className="flex items-center gap-2">
            <Input
              value={url}
              onChange={(e) => updateUrl(i, e.target.value)}
              placeholder="https://example.com/docs"
              className="flex-1"
            />
            <button type="button" onClick={() => removeUrl(i)} className="text-muted-foreground hover:text-red-400">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
        <Button type="button" variant="ghost" size="sm" onClick={addUrl} className="gap-1.5">
          <Plus className="w-3.5 h-3.5" /> Add URL
        </Button>
      </div>

      {/* Summary */}
      {(files.length > 0 || validUrlCount > 0) && (
        <p className="text-xs text-muted-foreground">
          {files.length > 0 && `${files.length} file(s) (${(totalSize / 1024 / 1024).toFixed(1)} MB)`}
          {files.length > 0 && validUrlCount > 0 && " + "}
          {validUrlCount > 0 && `${validUrlCount} URL(s)`}
        </p>
      )}
    </div>
  );
}
