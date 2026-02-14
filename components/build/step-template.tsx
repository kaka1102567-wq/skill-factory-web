"use client";

import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Template } from "@/types/build";

interface StepTemplateProps {
  selectedId: string | null;
  onSelect: (template: Template) => void;
}

export function StepTemplate({ selectedId, onSelect }: StepTemplateProps) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/templates")
      .then((res) => res.json())
      .then((data) => setTemplates(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        <span className="text-sm">Loading templates...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium text-foreground mb-1">Choose a template</h3>
        <p className="text-xs text-muted-foreground">
          Template defines the domain and default configuration for your skill build.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {templates.map((tpl) => {
          const isSelected = selectedId === tpl.id;
          return (
            <button
              key={tpl.id}
              type="button"
              onClick={() => onSelect(tpl)}
              className={cn(
                "relative p-4 rounded-xl border text-left transition-all",
                "hover:border-indigo-500/50 hover:bg-indigo-500/5",
                isSelected
                  ? "border-indigo-500 bg-indigo-500/10"
                  : "border-border bg-card",
              )}
            >
              {isSelected && (
                <div className="absolute top-3 right-3 w-5 h-5 rounded-full bg-indigo-500 flex items-center justify-center">
                  <Check className="w-3 h-3 text-white" />
                </div>
              )}
              <div className="text-2xl mb-2">{tpl.icon}</div>
              <h4 className="text-sm font-semibold text-foreground">{tpl.name}</h4>
              <p className="text-xs text-muted-foreground mt-0.5">{tpl.domain}</p>
              {tpl.description && (
                <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                  {tpl.description}
                </p>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
