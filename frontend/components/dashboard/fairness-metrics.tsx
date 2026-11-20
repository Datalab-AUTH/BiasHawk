"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BotMessageSquare, LoaderCircle, ShieldAlert, ShieldCheck } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Bias metrics from `analysis_results`: one card per feature (or per "A_&_B"
 * intersection) in each analysis, with its verdict, the numbers behind it and
 * an Explanation button.
 *
 * The shapes differ between analyses and older runs can lack fields, so every
 * builder here is defensive: anything it cannot read is skipped rather than
 * crashing the page.
 */

// Pass/fail rules, the same as backend/core/analysis/thresholds.py. The params
// stored with a run win; these cover results saved before a param existed.
const STATISTICAL_PARITY_MAX = 0.1; // SP <= 0.10 is acceptable, above is a problem
const DISPARATE_IMPACT_MIN = 0.8; // DI is acceptable from 0.80 ...
const DISPARATE_IMPACT_MAX = 1.25; // ... to 1.25, both inclusive

// The most bars one chart draws; the rest are summarised in a note.
const MAX_BARS = 20;

type Section = { params?: Record<string, unknown>; results?: Record<string, unknown> };

type Stat = { label: string; value: string; ok: boolean | null; rule: string };

type ChartSpec = {
  caption: string;
  unit: string;
  data: { group: string; value: number }[];
  format: (value: number) => string;
  domainMax?: number;
  /** A threshold drawn as a dashed line; bars on the wrong side are flagged. */
  reference?: number;
  isBad?: (value: number) => boolean;
  note?: string;
};

type MetricCard = {
  feature: string;
  ok: boolean | null;
  stats: Stat[];
  chart?: ChartSpec;
  note?: string;
};

// ---------------------------------------------------------------------------
// reading the results
// ---------------------------------------------------------------------------

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function param(section: Section, key: string, fallback: number): number {
  const value = section.params?.[key];
  return isNumber(value) ? value : fallback;
}

function numericEntries(record: Record<string, unknown> | null): [string, number][] {
  if (!record) return [];
  return Object.entries(record).filter((entry): entry is [string, number] => isNumber(entry[1]));
}

/** Intersections are stored as "a_&_b"; show "a & b". */
function label(name: string): string {
  return name.replaceAll("_&_", " & ");
}

/** Two decimals, as the backend rounds, so a 0.1000001 gap cannot fail a 0.10 limit. */
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

const fixed2 = (value: number) => value.toFixed(2);
// One decimal below 10% so a 0.5% group does not read as 0% or 1%.
const percent = (value: number) =>
  `${(value * 100).toFixed(value > 0 && value < 0.1 ? 1 : 0)}%`;

function errorCard(feature: string, error: unknown): MetricCard | null {
  return typeof error === "string" && error
    ? { feature, ok: null, stats: [], note: `Could not be computed: ${error}` }
    : null;
}

function chartOf(
  entries: [string, number][],
  spec: Omit<ChartSpec, "data" | "note">,
  order: "asc" | "desc" = "desc"
): ChartSpec {
  const sorted = [...entries].sort((a, b) => (order === "asc" ? a[1] - b[1] : b[1] - a[1]));
  const shown = sorted.slice(0, MAX_BARS);
  return {
    ...spec,
    data: shown.map(([group, value]) => ({ group, value })),
    note:
      sorted.length > shown.length
        ? `Showing ${order === "asc" ? "the smallest" : "the top"} ${shown.length} of ${sorted.length}.`
        : undefined,
  };
}

function fairnessCards(section: Section): MetricCard[] {
  const spMax = param(section, "parity_threshold", STATISTICAL_PARITY_MAX);
  const diMin = param(section, "impact_threshold", DISPARATE_IMPACT_MIN);
  const diMax = param(section, "impact_upper_threshold", DISPARATE_IMPACT_MAX);

  return Object.entries(section.results ?? {}).flatMap(([feature, raw]) => {
    const metrics = asRecord(raw);
    if (!metrics) return [];
    const failed = errorCard(feature, metrics.error);
    if (failed) return [failed];

    const sp = metrics["Statistical Parity"];
    const di = metrics["Disparate Impact Ratio"];
    if (!isNumber(sp) || !isNumber(di)) return [];

    const spOk = sp <= spMax;
    const diOk = di >= diMin && di <= diMax;
    const rates = numericEntries(asRecord(metrics["Favorable Probabilities"]));

    return [
      {
        feature,
        ok: spOk && diOk,
        stats: [
          {
            label: "Disparate Impact",
            value: fixed2(di),
            ok: diOk,
            rule: `acceptable ${fixed2(diMin)} to ${fixed2(diMax)}`,
          },
          {
            label: "Statistical Parity",
            value: fixed2(sp),
            ok: spOk,
            rule: `acceptable up to ${fixed2(spMax)}`,
          },
        ],
        chart: rates.length
          ? chartOf(rates, {
              caption: "Favourable-outcome rate by group",
              unit: "Favourable rate",
              format: percent,
              domainMax: 1,
            })
          : undefined,
      },
    ];
  });
}

function performanceCards(section: Section): MetricCard[] {
  const limit = param(section, "disparity_threshold", 0.2);

  return Object.entries(section.results ?? {}).flatMap(([feature, raw]) => {
    const groups = asRecord(raw);
    if (!groups) return [];
    const failed = errorCard(feature, groups.error);
    if (failed) return [failed];

    const scores = numericEntries(groups);
    const unscored = Object.keys(groups).length - scores.length;
    const unscoredNote = unscored
      ? `${unscored} group${unscored === 1 ? "" : "s"} had too little data to score.`
      : undefined;

    if (scores.length < 2) {
      return [
        {
          feature,
          ok: null,
          stats: [],
          note: ["Fewer than two groups had enough data to compare.", unscoredNote]
            .filter(Boolean)
            .join(" "),
        },
      ];
    }

    const values = scores.map(([, value]) => value);
    const gap = round2(Math.max(...values) - Math.min(...values));
    const ok = gap <= limit;

    return [
      {
        feature,
        ok,
        stats: [
          { label: "F1-score gap", value: fixed2(gap), ok, rule: `acceptable up to ${fixed2(limit)}` },
        ],
        chart: chartOf(scores, {
          caption: "F1-score by group",
          unit: "F1-score",
          format: fixed2,
          domainMax: 1,
        }),
        note: unscoredNote,
      },
    ];
  });
}

function representationCards(section: Section): MetricCard[] {
  const minPct = param(section, "min_pct", 0.01);

  return Object.entries(section.results ?? {}).flatMap(([feature, raw]) => {
    const groups = asRecord(raw);
    if (!groups) return [];
    const failed = errorCard(feature, groups.error);
    if (failed) return [failed];

    const shares = Object.entries(groups).flatMap(([group, info]): [string, number][] => {
      const share = asRecord(info)?.percentage;
      return isNumber(share) ? [[group, share]] : [];
    });
    if (!shares.length) return [];

    const smallest = Math.min(...shares.map(([, share]) => share));
    const ok = smallest >= minPct;

    return [
      {
        feature,
        ok,
        stats: [
          {
            label: "Smallest group",
            value: percent(smallest),
            ok,
            rule: `acceptable from ${percent(minPct)} of rows`,
          },
        ],
        // Smallest first: the under-represented groups are the point.
        chart: chartOf(
          shares,
          {
            caption: "Share of rows by group",
            unit: "Share of rows",
            format: percent,
            reference: minPct,
            isBad: (value) => value < minPct,
          },
          "asc"
        ),
      },
    ];
  });
}

function proxyCards(section: Section): MetricCard[] {
  const limit = param(section, "threshold", 0.7);

  return Object.entries(section.results ?? {}).flatMap(([feature, raw]) => {
    const scores = numericEntries(asRecord(raw));
    if (!scores.length) return [];

    const strongest = Math.max(...scores.map(([, value]) => value));
    const ok = strongest <= limit;

    return [
      {
        feature,
        ok,
        stats: [
          {
            label: "Strongest association",
            value: fixed2(strongest),
            ok,
            rule: `acceptable up to ${fixed2(limit)}`,
          },
        ],
        chart: chartOf(scores, {
          caption: "Association with the other columns",
          unit: "Association",
          format: fixed2,
          domainMax: 1,
          reference: limit,
          isBad: (value) => value > limit,
        }),
      },
    ];
  });
}

function predictabilityCards(section: Section): MetricCard[] {
  const limit = param(section, "threshold", 0.5);

  return Object.entries(section.results ?? {}).flatMap(([feature, raw]): MetricCard[] => {
    if (typeof raw === "string") return [{ feature, ok: null, stats: [], note: raw }];
    if (!isNumber(raw)) return [];
    const ok = raw <= limit;
    return [
      {
        feature,
        ok,
        stats: [
          {
            label: "Prediction accuracy",
            value: percent(raw),
            ok,
            rule: `acceptable up to ${percent(limit)}`,
          },
        ],
        note: `How well the other columns predict '${feature}'. High accuracy means they encode it.`,
      },
    ];
  });
}

const SECTIONS: { key: string; label: string; build: (section: Section) => MetricCard[] }[] = [
  { key: "fairness_metrics", label: "Fairness metrics", build: fairnessCards },
  {
    key: "intersectional_fairness_metrics",
    label: "Fairness metrics (intersectional)",
    build: fairnessCards,
  },
  { key: "performance_discrimination", label: "Performance disparity", build: performanceCards },
  {
    key: "intersectional_performance_discrimination",
    label: "Performance disparity (intersectional)",
    build: performanceCards,
  },
  { key: "sensitive_representativity", label: "Group representation", build: representationCards },
  {
    key: "intersectional_sensitive_representativity",
    label: "Group representation (intersectional)",
    build: representationCards,
  },
  { key: "proxy_identification", label: "Proxy correlation", build: proxyCards },
  {
    key: "sensitive_predictability",
    label: "Sensitive feature predictability",
    build: predictabilityCards,
  },
];

// ---------------------------------------------------------------------------
// rendering
// ---------------------------------------------------------------------------

function Verdict({ ok }: { ok: boolean | null }) {
  if (ok === null) return <Badge tone="neutral">Not assessed</Badge>;
  return ok ? (
    <Badge tone="success">
      <ShieldCheck /> Pass
    </Badge>
  ) : (
    <Badge tone="danger">
      <ShieldAlert /> Flagged
    </Badge>
  );
}

function GroupChart({ chart }: { chart: ChartSpec }) {
  const bad = chart.isBad;
  return (
    <figure className="flex flex-col gap-1">
      <figcaption className="text-xs text-muted-foreground">
        {chart.caption}
        {chart.reference !== undefined ? " · dashed line marks the limit" : ""}
      </figcaption>
      {/* ~28px a row plus the axis, so every group keeps its label. */}
      <ResponsiveContainer width="100%" height={Math.max(96, chart.data.length * 28 + 36)}>
        <BarChart data={chart.data} layout="vertical" margin={{ left: 4, right: 20, top: 4, bottom: 4 }}>
          <XAxis
            type="number"
            domain={[0, chart.domainMax ?? "auto"]}
            tickFormatter={chart.format}
            tick={{ fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="group"
            width={130}
            interval={0}
            tickFormatter={label}
            tick={{ fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "var(--muted)" }}
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              fontSize: 12,
            }}
            labelFormatter={(group) => label(String(group))}
            formatter={(value) => [
              typeof value === "number"
                ? `${chart.format(value)}${bad?.(value) ? " (outside the limit)" : ""}`
                : String(value),
              chart.unit,
            ]}
          />
          {chart.reference !== undefined ? (
            <ReferenceLine x={chart.reference} stroke="var(--destructive)" strokeDasharray="4 3" />
          ) : null}
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {chart.data.map((entry) => (
              <Cell
                key={entry.group}
                fill={bad?.(entry.value) ? "var(--destructive)" : "var(--chart-bar, #0e6e7c)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {chart.note ? <p className="text-xs text-muted-foreground">{chart.note}</p> : null}
    </figure>
  );
}

/**
 * The Explanation button and its dialog. The text is fetched when the dialog
 * opens; `version` changes whenever the instance does, so a re-run assessment
 * is never explained from a cached answer about the old numbers.
 */
function ExplanationButton({
  instanceId,
  version,
  metric,
  metricLabel,
  feature,
}: {
  instanceId: string;
  version: string;
  metric: string;
  metricLabel: string;
  feature: string;
}) {
  const [open, setOpen] = useState(false);
  const explanation = useQuery({
    queryKey: ["bias-explanation", instanceId, version, metric, feature],
    queryFn: () =>
      api.get<{ explanation: string }>(
        `/instances/${instanceId}/bias-explanation?${new URLSearchParams({ metric, feature })}`
      ),
    enabled: open,
    staleTime: Infinity,
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <BotMessageSquare /> Explanation
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-mono">{label(feature)}</DialogTitle>
          <DialogDescription>{metricLabel}</DialogDescription>
        </DialogHeader>
        {explanation.isError ? (
          <p className="text-sm text-destructive">
            {explanation.error instanceof ApiError
              ? explanation.error.message
              : "The explanation could not be loaded."}
          </p>
        ) : explanation.data ? (
          <p className="text-sm leading-relaxed whitespace-pre-wrap">
            {explanation.data.explanation}
          </p>
        ) : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <LoaderCircle className="size-4 animate-spin" /> Loading the explanation…
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function MetricCardView({
  card,
  metric,
  metricLabel,
  instanceId,
  version,
}: {
  card: MetricCard;
  metric: string;
  metricLabel: string;
  instanceId: string;
  version: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-md border p-4",
        card.ok === false && "border-destructive/40"
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-sm font-medium">{label(card.feature)}</span>
        <Verdict ok={card.ok} />
      </div>

      {card.stats.length ? (
        <dl className="grid grid-cols-2 gap-3">
          {card.stats.map((stat) => (
            <div key={stat.label} className="flex flex-col gap-0.5">
              <dt className="text-xs text-muted-foreground">{stat.label}</dt>
              <dd className="flex items-center gap-1.5">
                <span className="text-2xl font-semibold tabular-nums">{stat.value}</span>
                {stat.ok === null ? null : stat.ok ? (
                  <ShieldCheck className="size-4 text-success" aria-label="Within the limit" />
                ) : (
                  <ShieldAlert className="size-4 text-destructive" aria-label="Outside the limit" />
                )}
              </dd>
              <dd className="text-xs text-muted-foreground">{stat.rule}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {card.chart ? <GroupChart chart={card.chart} /> : null}
      {card.note ? <p className="text-xs text-muted-foreground">{card.note}</p> : null}

      <div className="mt-auto flex justify-end pt-1">
        <ExplanationButton
          instanceId={instanceId}
          version={version}
          metric={metric}
          metricLabel={metricLabel}
          feature={card.feature}
        />
      </div>
    </div>
  );
}

export function FairnessMetrics({
  results,
  instanceId,
  version,
}: {
  results: Record<string, unknown>;
  instanceId: string;
  /** Changes whenever the instance does, e.g. its `updated_at`. */
  version: string;
}) {
  const sections = useMemo(
    () =>
      SECTIONS.flatMap(({ key, label: sectionLabel, build }) => {
        const section = asRecord(results?.[key]) as Section | null;
        const cards = section ? build(section) : [];
        return cards.length
          ? [{ key, label: sectionLabel, cards, flagged: cards.filter((c) => c.ok === false).length }]
          : [];
      }),
    [results]
  );

  const [active, setActive] = useState(0);

  if (!sections.length) return null;
  const activeIndex = Math.min(active, sections.length - 1);
  const current = sections[activeIndex];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Fairness metrics</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-1.5">
          {sections.map((section, index) => (
            <button
              key={section.key}
              type="button"
              onClick={() => setActive(index)}
              aria-pressed={index === activeIndex}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                index === activeIndex
                  ? "border-transparent bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:border-foreground/30"
              )}
            >
              {section.label}
              {section.flagged ? ` · ${section.flagged} flagged` : ""}
            </button>
          ))}
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {current.cards.map((card) => (
            <MetricCardView
              key={card.feature}
              card={card}
              metric={current.key}
              metricLabel={current.label}
              instanceId={instanceId}
              version={version}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
