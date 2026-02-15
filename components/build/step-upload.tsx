"use client";

import { useCallback, useRef, useState } from "react";
import { FileText, Link2, FileDown, Trash2, Upload, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TRANSCRIPT_EXTENSIONS = [".txt", ".md"];
const PDF_EXTENSIONS = [".pdf"];
const MAX_TRANSCRIPT_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_PDF_SIZE = 50 * 1024 * 1024; // 50MB
const MAX_URLS = 20;
const MAX_PDF_FILES = 5;

interface StepUploadProps {
  files: File[];
  urls: string[];
  onFilesChange: (files: File[]) => void;
  onUrlsChange: (urls: string[]) => void;
}

export function StepUpload({ files, urls, onFilesChange, onUrlsChange }: StepUploadProps) {
  const [dragOverTranscript, setDragOverTranscript] = useState(false);
  const [dragOverPdf, setDragOverPdf] = useState(false);
  const transcriptRef = useRef<HTMLInputElement>(null);
  const pdfRef = useRef<HTMLInputElement>(null);

  // Split files by type
  const transcripts = files.filter((f) => {
    const ext = "." + f.name.split(".").pop()?.toLowerCase();
    return TRANSCRIPT_EXTENSIONS.includes(ext);
  });
  const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));

  const addTranscripts = useCallback(
    (newFiles: FileList | File[]) => {
      const valid = Array.from(newFiles).filter((f) => {
        const ext = "." + f.name.split(".").pop()?.toLowerCase();
        return TRANSCRIPT_EXTENSIONS.includes(ext) && f.size <= MAX_TRANSCRIPT_SIZE;
      });
      onFilesChange([...files, ...valid]);
    },
    [files, onFilesChange],
  );

  const addPdfs = useCallback(
    (newFiles: FileList | File[]) => {
      const currentPdfCount = pdfs.length;
      const valid = Array.from(newFiles).filter((f) => {
        return f.name.toLowerCase().endsWith(".pdf") && f.size <= MAX_PDF_SIZE;
      });
      const allowed = valid.slice(0, MAX_PDF_FILES - currentPdfCount);
      onFilesChange([...files, ...allowed]);
    },
    [files, pdfs.length, onFilesChange],
  );

  const removeFile = (index: number) => {
    onFilesChange(files.filter((_, i) => i !== index));
  };

  // URL textarea handling
  const urlText = urls.join("\n");
  const handleUrlChange = (text: string) => {
    const parsed = text.split("\n").slice(0, MAX_URLS);
    onUrlsChange(parsed);
  };

  const validUrls = urls.filter((u) => u.trim().match(/^https?:\/\/.+/));
  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const sourceCount = transcripts.length + validUrls.length + pdfs.length;

  return (
    <div className="space-y-6">
      {/* Transcripts section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-foreground">Transcripts</span>
        </div>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOverTranscript(true); }}
          onDragLeave={() => setDragOverTranscript(false)}
          onDrop={(e) => { e.preventDefault(); setDragOverTranscript(false); if (e.dataTransfer.files.length > 0) addTranscripts(e.dataTransfer.files); }}
          onClick={() => transcriptRef.current?.click()}
          className={cn(
            "flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all",
            dragOverTranscript ? "border-blue-500 bg-blue-500/10" : "border-border hover:border-blue-500/50 hover:bg-muted/30",
          )}
        >
          <Upload className="w-6 h-6 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">Drop .txt or .md files — max 10MB/file</p>
          <input ref={transcriptRef} type="file" multiple accept={TRANSCRIPT_EXTENSIONS.join(",")} className="hidden"
            onChange={(e) => e.target.files && addTranscripts(e.target.files)} />
        </div>
        {transcripts.length > 0 && (
          <div className="space-y-1.5">
            {transcripts.map((file, i) => {
              const globalIdx = files.indexOf(file);
              return (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-card border border-border">
                  <FileText className="w-4 h-4 text-blue-400 shrink-0" />
                  <span className="text-sm text-foreground truncate flex-1">{file.name}</span>
                  <span className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(0)} KB</span>
                  <button type="button" onClick={() => removeFile(globalIdx)} className="text-muted-foreground hover:text-red-400">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* URLs section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Link2 className="w-4 h-4 text-emerald-400" />
          <span className="text-sm font-medium text-foreground">URLs</span>
        </div>
        <textarea
          value={urlText}
          onChange={(e) => handleUrlChange(e.target.value)}
          placeholder={"Paste URLs (one per line):\nhttps://blog.example.com/guide\nhttps://docs.example.com/api"}
          rows={4}
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
        />
        <div className="flex items-start gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground">
            URLs will be fetched and converted to text. JS-rendered sites (SPAs) may not work. Max {MAX_URLS} URLs.
          </p>
        </div>
      </div>

      {/* PDFs section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <FileDown className="w-4 h-4 text-orange-400" />
          <span className="text-sm font-medium text-foreground">PDF Documents</span>
        </div>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOverPdf(true); }}
          onDragLeave={() => setDragOverPdf(false)}
          onDrop={(e) => { e.preventDefault(); setDragOverPdf(false); if (e.dataTransfer.files.length > 0) addPdfs(e.dataTransfer.files); }}
          onClick={() => pdfRef.current?.click()}
          className={cn(
            "flex flex-col items-center justify-center gap-2 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all",
            dragOverPdf ? "border-orange-500 bg-orange-500/10" : "border-border hover:border-orange-500/50 hover:bg-muted/30",
          )}
        >
          <Upload className="w-6 h-6 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">Drop .pdf files — max 50MB/file, max {MAX_PDF_FILES} files</p>
          <input ref={pdfRef} type="file" multiple accept=".pdf" className="hidden"
            onChange={(e) => e.target.files && addPdfs(e.target.files)} />
        </div>
        {pdfs.length > 0 && (
          <div className="space-y-1.5">
            {pdfs.map((file, i) => {
              const globalIdx = files.indexOf(file);
              return (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-card border border-border">
                  <FileDown className="w-4 h-4 text-orange-400 shrink-0" />
                  <span className="text-sm text-foreground truncate flex-1">{file.name}</span>
                  <span className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(1)} MB</span>
                  <button type="button" onClick={() => removeFile(globalIdx)} className="text-muted-foreground hover:text-red-400">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
        <div className="flex items-start gap-1.5">
          <AlertCircle className="w-3.5 h-3.5 text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground">
            Text will be extracted automatically. Scanned/image PDFs may have limited extraction.
          </p>
        </div>
      </div>

      {/* Summary */}
      {sourceCount > 0 && (
        <div className="rounded-lg bg-muted/50 p-3 border border-border">
          <p className="text-xs text-muted-foreground">
            {transcripts.length > 0 && `${transcripts.length} transcript(s)`}
            {transcripts.length > 0 && (validUrls.length > 0 || pdfs.length > 0) && " + "}
            {validUrls.length > 0 && `${validUrls.length} URL(s)`}
            {validUrls.length > 0 && pdfs.length > 0 && " + "}
            {pdfs.length > 0 && `${pdfs.length} PDF(s)`}
            {" = "}
            <span className="text-foreground font-medium">{sourceCount} source(s)</span>
            {totalSize > 0 && ` (${(totalSize / 1024 / 1024).toFixed(1)} MB)`}
          </p>
        </div>
      )}
    </div>
  );
}
