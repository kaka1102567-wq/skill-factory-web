"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import type { Template } from "@/types/build";

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/templates")
      .then((res) => res.json())
      .then((data) => {
        setTemplates(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Templates</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Config templates có sẵn — chọn 1 khi tạo build mới
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {templates.map((tpl) => (
          <div
            key={tpl.id}
            className="p-5 rounded-xl bg-card border border-border hover:border-indigo-500/30 transition-colors"
          >
            <div className="flex items-center gap-3 mb-3">
              <span className="text-2xl">{tpl.icon}</span>
              <div>
                <h3 className="text-sm font-semibold text-foreground">{tpl.name}</h3>
                <p className="text-xs text-muted-foreground">{tpl.domain}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mb-3">{tpl.description}</p>
            <div className="text-xs text-muted-foreground">
              Đã dùng: {tpl.usage_count} lần
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
