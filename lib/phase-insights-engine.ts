export interface PhaseInsight {
  type: "good" | "warning" | "critical" | "info" | "tip";
  text: string;
}

export interface PhaseAction {
  text: string;
  priority: "high" | "medium" | "low";
}

export interface ScoreComponent {
  name: string;
  score: number;
  weight: number;
  detail: string;
  status: "good" | "warning" | "critical";
}

export interface MetricItem {
  label: string;
  value: string | number;
  unit?: string;
}

export interface CoverageData {
  overlap: number;
  unique: number;
  gap: number;
  total: number;
}

export interface PhaseAnalysis {
  summary: string;
  metrics: MetricItem[];
  breakdown: ScoreComponent[];
  insights: PhaseInsight[];
  actions: PhaseAction[];
  coverageData?: CoverageData;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function analyzeP0(result: any): PhaseAnalysis {
  const metrics = result?.metrics ?? {};
  const refs: unknown[] = metrics?.references ?? [];
  const refCount = Array.isArray(refs) ? refs.length : 0;
  const source: string = metrics?.source ?? "";

  const insights: PhaseInsight[] = [];

  if (refCount >= 10) {
    insights.push({ type: "good", text: `Baseline đa dạng với ${refCount} tài liệu tham khảo` });
  } else if (refCount === 0) {
    insights.push({ type: "critical", text: "Không có baseline" });
  } else if (refCount < 5) {
    insights.push({ type: "warning", text: `Chỉ ${refCount} tài liệu — verify sẽ hạn chế` });
  }

  if (source === "auto-discovery") {
    insights.push({ type: "info", text: "Baseline được tìm tự động" });
  }

  const metricItems: MetricItem[] = [
    { label: "Tài liệu", value: refCount },
    { label: "Nguồn", value: source || "—" },
  ];

  if (result?.atoms_count != null) {
    metricItems.push({ label: "Atoms", value: result.atoms_count });
  }

  const score: number = result?.quality_score ?? 0;
  const summary =
    refCount === 0
      ? "Không tìm thấy baseline"
      : refCount >= 10
        ? `${refCount} tài liệu baseline`
        : `${refCount} tài liệu baseline — hạn chế`;

  return { summary, metrics: metricItems, breakdown: [], insights, actions: [] };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function analyzeP1(result: any): PhaseAnalysis {
  const metrics = result?.metrics ?? {};
  const topicsFound: number = metrics?.topics_found ?? 0;
  const transcriptsAudited: number = metrics?.transcripts_audited ?? 1;
  const overlapCount: number | undefined = metrics?.overlap_count;
  const uniqueExpertCount: number | undefined = metrics?.unique_expert_count;
  const gapCount: number | undefined = metrics?.gap_count;
  const total: number | undefined = metrics?.total;

  const hasCoverage =
    overlapCount !== undefined &&
    uniqueExpertCount !== undefined &&
    gapCount !== undefined &&
    total !== undefined &&
    (total as number) > 0;

  const insights: PhaseInsight[] = [];
  const actions: PhaseAction[] = [];

  const topicsPerTranscript = transcriptsAudited > 0 ? topicsFound / transcriptsAudited : 0;

  if (topicsPerTranscript > 100) {
    insights.push({
      type: "info",
      text: `Input dài — ${Math.round(topicsPerTranscript)} topics/file là bình thường`,
    });
  }

  let coverageData: CoverageData | undefined;

  if (hasCoverage) {
    const t = total as number;
    const ov = overlapCount as number;
    const un = uniqueExpertCount as number;
    const gap = gapCount as number;
    const overlapRatio = t > 0 ? ov / t : 0;
    const uniqueRatio = t > 0 ? un / t : 0;
    const gapRatio = t > 0 ? gap / t : 0;

    coverageData = { overlap: ov, unique: un, gap, total: t };

    if (overlapRatio > 0.8) {
      insights.push({
        type: "info",
        text: `Transcript cover ${Math.round(overlapRatio * 100)}% baseline — toàn diện`,
      });
    }
    if (uniqueRatio < 0.1) {
      actions.push({ text: "Thêm transcript với góc nhìn thực chiến", priority: "medium" });
    }
    if (gapRatio > 0.5) {
      insights.push({ type: "critical", text: `Còn ${gap} lỗ hổng so với baseline` });
    } else if (gapRatio > 0.2) {
      insights.push({ type: "warning", text: `Còn ${gap} lỗ hổng so với baseline` });
    }
  }

  const totalScore: number = result?.quality_score ?? 0;

  // P1-only score breakdown
  const densityScore = Math.min(100, topicsPerTranscript > 0 ? Math.min(topicsFound / 5, 100) : 50);
  const densityWeight = 0.3;

  const breakdown: ScoreComponent[] = [
    {
      name: "Density",
      score: densityScore,
      weight: 30,
      detail: `${topicsFound} topics / ${transcriptsAudited} files`,
      status: densityScore >= 70 ? "good" : densityScore >= 50 ? "warning" : "critical",
    },
  ];

  if (hasCoverage) {
    const t = total as number;
    const ov = overlapCount as number;
    const un = uniqueExpertCount as number;
    const gap = gapCount as number;
    const gapRatio = t > 0 ? gap / t : 0;
    const balanceScore = Math.max(0, Math.round((1 - gapRatio) * 100));
    const balanceWeight = 0.25;

    breakdown.push({
      name: "Balance",
      score: balanceScore,
      weight: 25,
      detail: `${ov} overlap / ${un} unique / ${gap} gap`,
      status: balanceScore >= 70 ? "good" : balanceScore >= 50 ? "warning" : "critical",
    });

    const estimatedRemainder =
      (totalScore - densityScore * densityWeight - balanceScore * balanceWeight) / 0.45;
    const clampedEstimate = Math.max(0, Math.min(100, estimatedRemainder));

    breakdown.push({
      name: "Depth + Category",
      score: Math.round(clampedEstimate),
      weight: 45,
      detail: "(ước lượng)",
      status: clampedEstimate >= 70 ? "good" : clampedEstimate >= 50 ? "warning" : "critical",
    });
  } else {
    const estimatedRemainder = (totalScore - densityScore * densityWeight) / 0.7;
    const clampedEstimate = Math.max(0, Math.min(100, estimatedRemainder));
    breakdown.push({
      name: "Depth + Category",
      score: Math.round(clampedEstimate),
      weight: 70,
      detail: "(ước lượng)",
      status: clampedEstimate >= 70 ? "good" : clampedEstimate >= 50 ? "warning" : "critical",
    });
  }

  const metricItems: MetricItem[] = [
    { label: "Topics", value: topicsFound },
    { label: "Transcripts", value: transcriptsAudited },
    { label: "Topics/file", value: Math.round(topicsPerTranscript) },
  ];
  if (hasCoverage) {
    metricItems.push(
      { label: "Overlap", value: overlapCount as number },
      { label: "Unique", value: uniqueExpertCount as number },
      { label: "Gap", value: gapCount as number }
    );
  }

  const summary = `${topicsFound} topics từ ${transcriptsAudited} transcript`;

  return { summary, metrics: metricItems, breakdown, insights, actions, coverageData };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function analyzeP2(result: any): PhaseAnalysis {
  const metrics = result?.metrics ?? {};
  const totalAtoms: number = metrics?.total_atoms ?? 0;
  const transcriptAtoms: number = metrics?.transcript_atoms ?? 0;
  const gapFillAtoms: number = metrics?.gap_fill_atoms ?? 0;
  const codeAtoms: number = metrics?.code_atoms ?? 0;
  const avgConfidence: number = metrics?.avg_confidence ?? 0;

  const insights: PhaseInsight[] = [];

  if (gapFillAtoms > 0) {
    insights.push({ type: "info", text: `Bổ sung ${gapFillAtoms} atoms từ baseline` });
  }
  if (codeAtoms > 0) {
    insights.push({ type: "info", text: `Phát hiện ${codeAtoms} code patterns` });
  }
  if (avgConfidence > 0.9) {
    insights.push({
      type: "good",
      text: `Confidence ${Math.round(avgConfidence * 100)}% — rất chính xác`,
    });
  } else if (avgConfidence > 0 && avgConfidence < 0.7) {
    insights.push({
      type: "warning",
      text: `Confidence thấp (${Math.round(avgConfidence * 100)}%)`,
    });
  }

  const metricItems: MetricItem[] = [
    { label: "Total atoms", value: totalAtoms },
    { label: "Transcript", value: transcriptAtoms },
    { label: "Gap fill", value: gapFillAtoms },
    { label: "Code", value: codeAtoms },
    { label: "Confidence", value: `${Math.round(avgConfidence * 100)}%` },
  ];

  const summary = `${totalAtoms} atoms extracted`;

  return { summary, metrics: metricItems, breakdown: [], insights, actions: [] };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function analyzeP3(result: any): PhaseAnalysis {
  const metrics = result?.metrics ?? {};
  const inputAtoms: number = metrics?.input_atoms ?? 0;
  const outputAtoms: number = metrics?.output_atoms ?? 0;
  const duplicatesMerged: number = metrics?.duplicates_merged ?? 0;
  const conflictsTotal: number = metrics?.conflicts_total ?? 0;
  const conflictsUnresolved: number = metrics?.conflicts_unresolved ?? 0;
  const crossSourceContradictions: number = metrics?.cross_source_contradictions ?? 0;

  const insights: PhaseInsight[] = [];
  const actions: PhaseAction[] = [];

  const keptPct = inputAtoms > 0 ? Math.round((outputAtoms / inputAtoms) * 100) : 0;
  insights.push({
    type: "info",
    text: `Giữ lại ${outputAtoms}/${inputAtoms} atoms (${keptPct}%)`,
  });

  const dedupRate = inputAtoms > 0 ? duplicatesMerged / inputAtoms : 0;
  if (dedupRate > 0.6) {
    insights.push({ type: "tip", text: `Dedup rate cao (${Math.round(dedupRate * 100)}%) — data có nhiều trùng lặp` });
  }

  if (conflictsUnresolved > 0) {
    insights.push({ type: "critical", text: `${conflictsUnresolved} conflicts chưa giải quyết` });
  }
  if (crossSourceContradictions > 0) {
    insights.push({ type: "warning", text: `${crossSourceContradictions} mâu thuẫn giữa các nguồn` });
  }

  const metricItems: MetricItem[] = [
    { label: "Input atoms", value: inputAtoms },
    { label: "Output atoms", value: outputAtoms },
    { label: "Duplicates", value: duplicatesMerged },
    { label: "Conflicts", value: conflictsTotal },
    { label: "Unresolved", value: conflictsUnresolved },
  ];

  const summary = `${outputAtoms}/${inputAtoms} atoms giữ lại (${keptPct}%)`;

  return { summary, metrics: metricItems, breakdown: [], insights, actions };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function analyzeP4(result: any): PhaseAnalysis {
  const metrics = result?.metrics ?? {};
  const totalAtoms: number = metrics?.total_atoms ?? 0;
  const sampled: number = metrics?.sampled ?? 0;
  const verified: number = metrics?.verified ?? 0;
  const updated: number = metrics?.updated ?? 0;
  const flagged: number = metrics?.flagged ?? 0;
  const samplePct: number = metrics?.sample_pct ?? 0;

  const insights: PhaseInsight[] = [];
  const actions: PhaseAction[] = [];

  if (samplePct === 30) {
    insights.push({ type: "warning", text: "Chỉ verify 30% (Draft tier)" });
  } else if (samplePct === 100) {
    insights.push({ type: "good", text: "Verify 100% (Premium tier)" });
  }

  if (verified === sampled && flagged === 0 && sampled > 0) {
    insights.push({ type: "good", text: "100% pass" });
  } else if (flagged > 0) {
    insights.push({ type: "warning", text: `${flagged} atoms bị flag` });
  }

  if (samplePct < 100) {
    actions.push({ text: "Chạy lại với tier cao hơn", priority: "medium" });
  }

  const metricItems: MetricItem[] = [
    { label: "Total", value: totalAtoms },
    { label: "Sampled", value: sampled },
    { label: "Verified", value: verified },
    { label: "Updated", value: updated },
    { label: "Flagged", value: flagged },
    { label: "Sample %", value: `${samplePct}%` },
  ];

  const summary = `Verify ${sampled}/${totalAtoms} atoms (${samplePct}%)`;

  return { summary, metrics: metricItems, breakdown: [], insights, actions };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function analyzeP5(result: any): PhaseAnalysis {
  const metrics = result?.metrics ?? {};
  const pillars: number = metrics?.pillars ?? 0;
  const knowledgeFiles: number = metrics?.knowledge_files ?? 0;
  const atomsIncluded: number = metrics?.atoms_included ?? 0;
  const atomsFlagged: number = metrics?.atoms_flagged ?? 0;
  const platformsBuilt: string[] | string = metrics?.platforms_built ?? [];

  const insights: PhaseInsight[] = [];
  const actions: PhaseAction[] = [];

  insights.push({ type: "info", text: `${pillars} pillars kiến thức` });

  if (atomsFlagged > 0) {
    insights.push({ type: "warning", text: `${atomsFlagged} atoms bị flag trong output` });
  }

  const platformList = Array.isArray(platformsBuilt)
    ? platformsBuilt
    : typeof platformsBuilt === "string"
      ? [platformsBuilt]
      : [];

  if (platformList.length > 0) {
    insights.push({ type: "good", text: `Đóng gói cho: ${platformList.join(", ")}` });
  }

  const metricItems: MetricItem[] = [
    { label: "Pillars", value: pillars },
    { label: "Files", value: knowledgeFiles },
    { label: "Atoms", value: atomsIncluded },
    { label: "Flagged", value: atomsFlagged },
  ];

  const summary = `${pillars} pillars, ${atomsIncluded} atoms, ${platformList.length} platform`;

  return { summary, metrics: metricItems, breakdown: [], insights, actions };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function analyzePhase(phaseId: string, result: any): PhaseAnalysis {
  switch (phaseId) {
    case "p0":
      return analyzeP0(result);
    case "p1":
      return analyzeP1(result);
    case "p2":
      return analyzeP2(result);
    case "p3":
      return analyzeP3(result);
    case "p4":
      return analyzeP4(result);
    case "p5":
      return analyzeP5(result);
    default: {
      const score: number = result?.quality_score ?? 0;
      return {
        summary: `Phase ${phaseId} — score ${Math.round(score)}`,
        metrics: [],
        breakdown: [],
        insights: [],
        actions: [],
      };
    }
  }
}
