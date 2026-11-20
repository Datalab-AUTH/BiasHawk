"use client";

import { useMemo } from "react";

import type { DriftEvent, DriftRecord, DriftWarning } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TONE: Record<string, "danger" | "warning" | "neutral"> = {
  high: "danger",
  critical: "danger",
  medium: "warning",
  low: "neutral",
};

function tone(severity: string | undefined) {
  return TONE[(severity ?? "").toLowerCase()] ?? "neutral";
}

export function DriftSummary({ record }: { record: DriftRecord }) {
  // The handler stores the data-drift warnings as a JSON string, so parse
  // defensively rather than assuming either shape.
  const warnings = useMemo<DriftWarning[]>(() => {
    const raw = record.data_drift_warnings;
    if (!raw) return [];
    if (Array.isArray(raw)) return raw as DriftWarning[];
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }, [record.data_drift_warnings]);

  const events: DriftEvent[] = Array.isArray(record.bias_drift_events)
    ? record.bias_drift_events
    : [];

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Card>
          <CardContent className="flex items-center gap-3 p-5">
            <Badge tone={record.drift_detected ? "danger" : "success"}>
              {record.drift_detected ? "Data drift detected" : "No data drift"}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {warnings.length} {warnings.length === 1 ? "warning" : "warnings"}
            </span>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-5">
            <Badge tone={record.bias_drift_detected ? "danger" : "success"}>
              {record.bias_drift_detected ? "Bias drift detected" : "No bias drift"}
            </Badge>
            <span className="text-sm text-muted-foreground">
              {events.length} {events.length === 1 ? "event" : "events"}
            </span>
          </CardContent>
        </Card>
      </div>

      <p className="text-sm text-muted-foreground">
        Comparing <span className="font-medium text-foreground">{record.initial_instance_name}</span>{" "}
        against <span className="font-medium text-foreground">{record.comparison_instance_name}</span>.
      </p>

      {warnings.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Data drift</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {warnings.map((warning, index) => (
                <li key={index} className="flex flex-col gap-1 rounded-md border px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={tone(warning.severity)}>{warning.severity ?? ","}</Badge>
                    <span className="text-sm font-medium">{warning.test_name}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {warning.feature}
                    </span>
                  </div>
                  {warning.description ? (
                    <p className="text-sm text-muted-foreground">{warning.description}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {events.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Bias drift</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {events.map((event, index) => (
                <li key={index} className="flex flex-col gap-1 rounded-md border px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={tone(event.severity)}>{event.severity ?? ","}</Badge>
                    <span className="text-sm font-medium">{event.metric}</span>
                    <span className="font-mono text-xs text-muted-foreground">{event.feature}</span>
                  </div>
                  {event.description ? (
                    <p className="text-sm text-muted-foreground">{event.description}</p>
                  ) : null}
                  {typeof event.baseline_value === "number" &&
                  typeof event.current_value === "number" ? (
                    <p className="font-mono text-xs tabular-nums text-muted-foreground">
                      {event.baseline_value.toFixed(3)} → {event.current_value.toFixed(3)}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
