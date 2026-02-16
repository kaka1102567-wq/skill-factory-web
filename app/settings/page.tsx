"use client";

import { useState, useEffect } from "react";
import {
  Key, Terminal, Bell, Trash2, Save, Loader2,
  Check, AlertCircle, TestTube, HardDrive
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface Settings {
  [key: string]: string;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ type: string; ok: boolean; msg: string } | null>(null);
  const [cleanupResult, setCleanupResult] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/settings")
      .then((res) => res.json())
      .then((data) => {
        setSettings(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const update = (key: string, value: string) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error("Save failed");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError("Không thể lưu settings");
    }
    setSaving(false);
  };

  const handleTestTelegram = async () => {
    setTestResult(null);
    try {
      const res = await fetch("/api/settings/test-telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: settings.notification_telegram_token,
          chat_id: settings.notification_telegram_chat_id,
        }),
      });
      const data = await res.json();
      setTestResult({ type: "telegram", ok: data.ok, msg: data.ok ? "Gửi test thành công!" : "Thất bại" });
    } catch {
      setTestResult({ type: "telegram", ok: false, msg: "Không thể kết nối" });
    }
  };

  const handleCleanup = async () => {
    try {
      const res = await fetch("/api/settings/cleanup", { method: "POST" });
      const data = await res.json();
      setCleanupResult(`Đã xóa ${data.deleted} builds, giải phóng ${data.freedMB}MB`);
      setTimeout(() => setCleanupResult(null), 5000);
    } catch {
      setCleanupResult("Cleanup thất bại");
      setTimeout(() => setCleanupResult(null), 3000);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">API keys, pipeline config, notifications</p>
        </div>
        <Button onClick={handleSave} disabled={saving} className="gap-2">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? "Đã lưu!" : "Lưu Settings"}
        </Button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-sm text-red-400">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* API Keys */}
      <Section icon={Key} title="API Keys">
        <Field label="Claude API Key" value={settings.claude_api_key} onChange={(v) => update("claude_api_key", v)} placeholder="sk-ant-..." type="password" />
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">API Base URL</label>
          <Input
            type="text"
            value={settings.claude_base_url || ""}
            onChange={(e) => update("claude_base_url", e.target.value)}
            placeholder="https://api.anthropic.com (default)"
            className="text-sm"
          />
          <p className="text-xs text-muted-foreground mt-1">
            Leave empty for direct Anthropic. Set URL for alternative providers (e.g. https://claudible.io)
          </p>
        </div>
        <Field label="Gemini API Key" value={settings.gemini_api_key} onChange={(v) => update("gemini_api_key", v)} placeholder="AIza..." type="password" />
      </Section>

      {/* Pipeline */}
      <Section icon={Terminal} title="Pipeline">
        <Field label="Python Path" value={settings.python_path} onChange={(v) => update("python_path", v)} placeholder="python3" />
        <Field label="Pipeline Path" value={settings.pipeline_path} onChange={(v) => update("pipeline_path", v)} placeholder="./pipeline" />
        <Field label="Max Concurrent Builds" value={settings.max_concurrent_builds} onChange={(v) => update("max_concurrent_builds", v)} placeholder="2" />
        <Field label="Default Quality Tier" value={settings.default_quality_tier} onChange={(v) => update("default_quality_tier", v)} placeholder="standard" />
        <div>
          <label className="text-xs font-medium text-muted-foreground block mb-1">Light Model (for Dedup + Verify)</label>
          <select
            value={settings.claude_model_light || "claude-haiku-4-5-20251001"}
            onChange={(e) => update("claude_model_light", e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors"
          >
            <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5 (cost saving)</option>
            <option value="claude-sonnet-4-20250514">Claude Sonnet 4 (higher quality)</option>
          </select>
          <p className="text-xs text-muted-foreground mt-1">
            Light model used for P3 (Dedup) and P4 (Verify). Haiku saves 67% cost per request.
          </p>
        </div>
      </Section>

      {/* Notifications */}
      <Section icon={Bell} title="Telegram Notifications">
        <Field label="Bot Token" value={settings.notification_telegram_token} onChange={(v) => update("notification_telegram_token", v)} placeholder="123456:ABC..." type="password" />
        <Field label="Chat ID" value={settings.notification_telegram_chat_id} onChange={(v) => update("notification_telegram_chat_id", v)} placeholder="-100..." />
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={handleTestTelegram} className="gap-1.5 text-xs">
            <TestTube className="w-3 h-3" /> Test Connection
          </Button>
          {testResult && (
            <span className={cn("text-xs", testResult.ok ? "text-emerald-400" : "text-red-400")}>
              {testResult.msg}
            </span>
          )}
        </div>
      </Section>

      {/* Maintenance */}
      <Section icon={HardDrive} title="Maintenance">
        <Field label="Auto-cleanup (days)" value={settings.auto_cleanup_days} onChange={(v) => update("auto_cleanup_days", v)} placeholder="30" />
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={handleCleanup} className="gap-1.5 text-xs">
            <Trash2 className="w-3 h-3" /> Cleanup Now
          </Button>
          {cleanupResult && <span className="text-xs text-emerald-400">{cleanupResult}</span>}
        </div>
      </Section>
    </div>
  );
}

function Section({ icon: Icon, title, children }: { icon: React.ComponentType<{ className?: string }>; title: string; children: React.ReactNode }) {
  return (
    <div className="p-5 rounded-xl bg-card border border-border space-y-4">
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-indigo-400" />
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Field({ label, value, onChange, placeholder, type = "text" }: { label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string }) {
  return (
    <div>
      <label className="text-xs font-medium text-muted-foreground block mb-1">{label}</label>
      <Input type={type} value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="text-sm" />
    </div>
  );
}
