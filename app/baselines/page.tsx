"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Database, RefreshCw, Trash2, Plus, Loader2,
  CheckCircle2, Clock, AlertCircle, Globe
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface Baseline {
  id: string;
  domain: string;
  name: string;
  config_path: string | null;
  seekers_output_dir: string | null;
  status: string;
  source_urls: string | null;
  refs_count: number;
  topics_count: number;
  last_scraped_at: string | null;
  created_at: string;
}

const STATUS_ICONS: Record<string, { icon: typeof CheckCircle2; color: string }> = {
  ready: { icon: CheckCircle2, color: "text-emerald-400" },
  scraping: { icon: RefreshCw, color: "text-amber-400 animate-spin" },
  pending: { icon: Clock, color: "text-muted-foreground" },
  failed: { icon: AlertCircle, color: "text-red-400" },
};

export default function BaselinesPage() {
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newDomain, setNewDomain] = useState("");
  const [newName, setNewName] = useState("");
  const [newUrls, setNewUrls] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchBaselines = useCallback(() => {
    fetch("/api/baselines")
      .then((r) => r.json())
      .then((data) => { setBaselines(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { fetchBaselines(); }, [fetchBaselines]);

  const handleCreate = async () => {
    if (!newDomain.trim() || !newName.trim()) return;
    setCreating(true);
    try {
      await fetch("/api/baselines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain: newDomain.trim(),
          name: newName.trim(),
          source_urls: newUrls.split("\n").map((u) => u.trim()).filter(Boolean),
        }),
      });
      setShowAdd(false);
      setNewDomain("");
      setNewName("");
      setNewUrls("");
      fetchBaselines();
    } catch { /* ignore */ }
    setCreating(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this baseline?")) return;
    await fetch(`/api/baselines?id=${id}`, { method: "DELETE" });
    fetchBaselines();
  };

  const handleRescrape = async (bl: Baseline) => {
    await fetch("/api/baselines", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: bl.id, status: "scraping" }),
    });
    fetchBaselines();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Baselines</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage scraped documentation baselines for each domain
          </p>
        </div>
        <Button onClick={() => setShowAdd(!showAdd)} className="gap-2">
          <Plus className="w-4 h-4" />
          Add Baseline
        </Button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="p-5 rounded-xl bg-card border border-border space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Domain</label>
              <Input value={newDomain} onChange={(e) => setNewDomain(e.target.value)} placeholder="e.g. google-ads" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Name</label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Google Ads Documentation" />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Source URLs (one per line)</label>
            <textarea
              value={newUrls}
              onChange={(e) => setNewUrls(e.target.value)}
              placeholder={"https://support.google.com/google-ads\nhttps://developers.google.com/google-ads/api"}
              rows={3}
              className="w-full px-3 py-2 rounded-lg border border-border bg-background text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>
          <div className="flex gap-2">
            <Button onClick={handleCreate} disabled={creating || !newDomain.trim() || !newName.trim()} size="sm">
              {creating ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : null}
              Create
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowAdd(false)}>Cancel</Button>
          </div>
        </div>
      )}

      {/* Baselines list */}
      {baselines.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Database className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No baselines yet</p>
          <p className="text-xs mt-1">Create one or run a build to auto-generate</p>
        </div>
      ) : (
        <div className="space-y-3">
          {baselines.map((bl) => {
            const statusInfo = STATUS_ICONS[bl.status] || STATUS_ICONS.pending;
            const StatusIcon = statusInfo.icon;
            const urls: string[] = bl.source_urls ? JSON.parse(bl.source_urls) : [];

            return (
              <div key={bl.id} className="p-4 rounded-xl bg-card border border-border">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <StatusIcon className={cn("w-5 h-5 mt-0.5", statusInfo.color)} />
                    <div>
                      <h3 className="text-sm font-semibold text-foreground">{bl.name}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {bl.domain} | {bl.refs_count} refs | {bl.topics_count} topics
                      </p>
                      {bl.seekers_output_dir && (
                        <p className="text-xs text-emerald-400 mt-1">Baseline ready</p>
                      )}
                      {urls.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {urls.map((url, i) => (
                            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-muted text-xs text-muted-foreground">
                              <Globe className="w-3 h-3" />
                              {new URL(url).hostname}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRescrape(bl)}
                      className="text-xs gap-1"
                      disabled={bl.status === "scraping"}
                    >
                      <RefreshCw className="w-3 h-3" /> Re-scrape
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(bl.id)}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
                {bl.last_scraped_at && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Last scraped: {new Date(bl.last_scraped_at).toLocaleString()}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
