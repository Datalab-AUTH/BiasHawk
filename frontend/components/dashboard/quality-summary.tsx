"use client";

import type { QualityMetrics, QualityWarning, SensitiveFeature, Severity } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const SEVERITY_TONE: Record<Severity, "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

/** Whole-dataset figures, shown before the per-feature detail. */
export function DatasetStats({ metrics }: { metrics: QualityMetrics }) {
  const { total_rows, total_columns, duplicate_rows } = metrics.dataset;
  const duplicatePct = total_rows ? (duplicate_rows / total_rows) * 100 : 0;

  const stats = [
    { label: "Rows", value: total_rows.toLocaleString() },
    { label: "Columns", value: String(total_columns) },
    {
      label: "Duplicate rows",
      value: duplicate_rows.toLocaleString(),
      note: total_rows ? `${duplicatePct.toFixed(1)}%` : undefined,
      alarming: duplicatePct > 5,
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {stats.map((stat) => (
        <div key={stat.label} className="rounded-md border border-border px-4 py-3">
          <p className="text-xs text-muted-foreground">{stat.label}</p>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="text-xl font-semibold tabular-nums">{stat.value}</span>
            {stat.note ? (
              <span
                className={
                  stat.alarming ? "text-xs text-destructive" : "text-xs text-muted-foreground"
                }
              >
                {stat.note}
              </span>
            ) : null}
          </p>
        </div>
      ))}
    </div>
  );
}

export function WarningsList({ warnings }: { warnings: QualityWarning[] }) {
  if (!warnings.length) {
    return <p className="text-sm text-muted-foreground">No quality issues found.</p>;
  }

  // Worst first: a list ordered by severity is scannable, one in insertion
  // order is not.
  const order: Severity[] = ["high", "medium", "low"];
  const sorted = [...warnings].sort(
    (a, b) => order.indexOf(a.severity) - order.indexOf(b.severity)
  );

  return (
    <ul className="flex flex-col gap-2">
      {sorted.map((warning, index) => (
        <li
          key={`${warning.test_name}-${warning.feature}-${index}`}
          className="flex flex-col gap-1 rounded-md border border-border px-3 py-2.5"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={SEVERITY_TONE[warning.severity]}>{warning.severity}</Badge>
            <span className="text-sm font-medium">{warning.test_name}</span>
            <span className="font-mono text-xs text-muted-foreground">{warning.feature}</span>
          </div>
          <p className="text-sm text-muted-foreground">{warning.description}</p>
        </li>
      ))}
    </ul>
  );
}

/**
 * Detected sensitive features, highest assessment score first.
 *
 * Shows which detector fired: keyword matching and the model agreeing is a
 * stronger signal than either alone, and the difference is worth surfacing.
 */
/**
 * What the detector put forward, with its reasoning.
 *
 * A recommendation and nothing more: what actually gets measured is whatever
 * is selected in the picker, so this card says so rather than reading as the
 * current selection.
 */
export function SensitiveFeatures({
  features,
}: {
  features: Record<string, SensitiveFeature>;
}) {
  const entries = Object.entries(features).sort((a, b) => b[1].score - a[1].score);

  return (
    <Card>
      <CardHeader>
        <CardTitle>What the automatic analysis recommends</CardTitle>
        <p className="text-sm text-muted-foreground">
          Suggestions from the sensitive feature detector, not the selection. The assessment
          measures whichever columns are selected above.
        </p>
      </CardHeader>
      <CardContent>
        {!entries.length ? (
          <p className="text-sm text-muted-foreground">
            Nothing recommended yet. Run the detector above, or pick the columns yourself.
          </p>
        ) : (
        <ul className="flex flex-col gap-2">
          {entries.map(([name, feature]) => (
            <li key={name} className="flex flex-col gap-1.5 rounded-md border border-border px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-medium">{name}</span>
                <Badge tone={feature.score >= 80 ? "danger" : feature.score >= 60 ? "warning" : "neutral"}>
                  score {feature.score}
                </Badge>
                {feature.by_keyword ? <Badge tone="info">keyword</Badge> : null}
                {feature.by_llm ? <Badge tone="info">model</Badge> : null}
              </div>
              {feature.categories.length ? (
                <p className="text-xs text-muted-foreground">
                  {[...new Set(feature.categories)].join(", ")}
                </p>
              ) : null}
              {feature.summary ? (
                <p className="text-sm text-muted-foreground">{feature.summary}</p>
              ) : null}
            </li>
          ))}
        </ul>
        )}
      </CardContent>
    </Card>
  );
}
