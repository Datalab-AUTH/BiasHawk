"use client";

import type { RiskReportData } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const LEVEL_TONE: Record<string, "danger" | "warning" | "info" | "success"> = {
  CRITICAL: "danger",
  HIGH: "danger",
  MEDIUM: "warning",
  LOW: "success",
};

type Action = {
  risk_category?: string;
  risk_description?: string;
  priority?: number | string;
  severity?: string;
  recommended_actions?: string[];
  nist_subcategory?: string;
};

/** The headline verdict, before the long-form report. */
export function RiskSummary({ data }: { data: RiskReportData | Record<string, never> }) {
  const level = data?.overall_risk_level;
  if (!level) return null;

  const actions = (data.prioritized_actions ?? []) as Action[];
  const findings = data.critical_findings ?? [];

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardContent className="flex flex-wrap items-center gap-4 p-5">
          <div className="flex items-center gap-3">
            <Badge tone={LEVEL_TONE[level.level] ?? "neutral"} className="px-3 py-1 text-sm">
              {level.level}
            </Badge>
            <span className="text-2xl font-semibold tabular-nums">{level.score}</span>
            <span className="text-sm text-muted-foreground">/ 100</span>
          </div>
          <p className="min-w-0 flex-1 text-balance text-sm text-muted-foreground">
            {level.justification}
          </p>
        </CardContent>
      </Card>

      {findings.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Critical findings</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {findings.map((finding, index) => (
                <li key={index} className="flex gap-2 text-sm">
                  <span className="text-destructive">•</span>
                  <span>{finding}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {actions.length ? (
        <Card>
          <CardHeader>
            <CardTitle>Prioritised actions</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-3">
              {actions.map((action, index) => (
                <li key={index} className="rounded-md border px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">#{action.priority ?? index + 1}</Badge>
                    {action.severity ? (
                      <Badge tone={LEVEL_TONE[action.severity] ?? "neutral"}>
                        {action.severity}
                      </Badge>
                    ) : null}
                    <span className="font-mono text-xs text-muted-foreground">
                      {action.risk_category ?? action.nist_subcategory ?? ","}
                    </span>
                  </div>
                  {action.risk_description ? (
                    <p className="mt-1.5 text-sm">{action.risk_description}</p>
                  ) : null}
                  {action.recommended_actions?.length ? (
                    <ul className="mt-1.5 flex flex-col gap-1">
                      {action.recommended_actions.map((step, i) => (
                        <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                          <span>·</span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
