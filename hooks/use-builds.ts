"use client";

import { useState, useEffect, useCallback } from "react";
import type { Build } from "@/types/build";

interface UseBuildsOptions {
  status?: string;
  refreshInterval?: number;
}

export function useBuilds(options: UseBuildsOptions = {}) {
  const { status = "all", refreshInterval = 10000 } = options;
  const [builds, setBuilds] = useState<Build[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBuilds = useCallback(async () => {
    try {
      const res = await fetch(`/api/builds?status=${status}`);
      if (!res.ok) throw new Error("Failed to fetch builds");
      const data = await res.json();
      setBuilds(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    fetchBuilds();
    if (refreshInterval > 0) {
      const interval = setInterval(fetchBuilds, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchBuilds, refreshInterval]);

  return { builds, loading, error, refetch: fetchBuilds };
}
