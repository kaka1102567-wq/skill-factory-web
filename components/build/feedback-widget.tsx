"use client";

import { useState } from "react";
import { Star, CheckCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const ISSUE_TAGS = [
  "Missing topics",
  "Inaccurate information",
  "Description too vague",
  "Too few atoms",
  "Redundant content",
  "Wrong language",
];

export function FeedbackWidget({ buildId }: { buildId: string }) {
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [selectedIssues, setSelectedIssues] = useState<string[]>([]);
  const [feedback, setFeedback] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  function toggleIssue(issue: string) {
    setSelectedIssues((prev) =>
      prev.includes(issue) ? prev.filter((i) => i !== issue) : [...prev, issue]
    );
  }

  async function handleSubmit() {
    if (!rating) {
      setError("Please select a star rating.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const res = await fetch(`/api/builds/${buildId}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, feedback, issues: selectedIssues }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError((data as { error?: string }).error || "Submission failed.");
        return;
      }
      setSubmitted(true);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex flex-col items-center gap-2 py-8 text-center">
        <CheckCircle className="w-8 h-8 text-emerald-400" />
        <p className="text-sm font-medium">Thanks for your feedback!</p>
        <p className="text-xs text-muted-foreground">
          Your input helps improve future builds for this domain.
        </p>
      </div>
    );
  }

  const activeRating = hovered || rating;

  return (
    <div className="space-y-4 p-4 rounded-xl bg-card border border-border">
      <h3 className="text-sm font-semibold">Rate this build</h3>

      {/* Star rating */}
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            onClick={() => setRating(star)}
            onMouseEnter={() => setHovered(star)}
            onMouseLeave={() => setHovered(0)}
            className="focus:outline-none"
            aria-label={`Rate ${star} star${star !== 1 ? "s" : ""}`}
          >
            <Star
              className={cn(
                "w-6 h-6 transition-colors",
                star <= activeRating
                  ? "fill-amber-400 text-amber-400"
                  : "text-muted-foreground"
              )}
            />
          </button>
        ))}
      </div>

      {/* Issue chips */}
      <div className="flex flex-wrap gap-2">
        {ISSUE_TAGS.map((tag) => (
          <button
            key={tag}
            type="button"
            onClick={() => toggleIssue(tag)}
            className={cn(
              "px-3 py-1 rounded-full text-xs border transition-colors",
              selectedIssues.includes(tag)
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-muted text-muted-foreground border-border hover:border-primary"
            )}
          >
            {tag}
          </button>
        ))}
      </div>

      {/* Optional feedback text */}
      <textarea
        value={feedback}
        onChange={(e) => setFeedback(e.target.value)}
        placeholder="Optional: describe what could be improved..."
        rows={3}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground"
      />

      {error && <p className="text-xs text-destructive">{error}</p>}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitting}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
        Submit Feedback
      </button>
    </div>
  );
}
