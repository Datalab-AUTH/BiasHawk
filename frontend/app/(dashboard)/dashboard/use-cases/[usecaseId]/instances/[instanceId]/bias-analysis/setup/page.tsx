"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";

import { api } from "@/lib/api";
import { latestByKind, useJobs, useRefetchOnComplete, useRunJob } from "@/lib/jobs";
import { useSelection } from "@/lib/store";
import type { DatasetFile, InstanceDetail } from "@/lib/types";
import { AnalysisRow } from "@/components/dashboard/job-status";
import {
  BiasTargetFields,
  SensitiveFeaturePicker,
  ungroupableColumns,
} from "@/components/dashboard/bias-setup";
import { SensitiveFeatures } from "@/components/dashboard/quality-summary";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState, PageHeader } from "@/components/ui/primitives";
import { Skeleton } from "@/components/ui/skeleton";

/** Columns whose name reads like the thing being predicted. */
const LABEL_GUESS = /^(risk|label|target|outcome|approved|default)$/i;

type StoredSetup = {
  pickedFeatures: string[] | null;
  pickedLabel: string | null;
  favorable: string;
};

function setupStorageKey(instanceId: string) {
  return `biashawk:bias-setup:${instanceId}`;
}

/** Reads back a previous session's picks, if the browser still has them. */
function loadStoredSetup(instanceId: string | undefined): StoredSetup | null {
  if (!instanceId || typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(setupStorageKey(instanceId));
    return raw ? (JSON.parse(raw) as StoredSetup) : null;
  } catch {
    return null;
  }
}

export default function BiasAnalysisSetupPage() {
  const { usecaseId, instanceId } = useParams<{ usecaseId: string; instanceId: string }>();
  const seen = useRef(new Set<string>());

  // Null means "not chosen yet", so the detector's suggestions can still show
  // through. The moment the user picks, their choice is what counts and a
  // later detection run cannot overwrite it.
  //
  // Seeded from localStorage so a refresh restores what was picked instead of
  // falling back to the detector's suggestions again , a deselected feature
  // used to reappear the moment the page reloaded.
  const [pickedFeatures, setPickedFeatures] = useState<string[] | null>(
    () => loadStoredSetup(instanceId)?.pickedFeatures ?? null
  );
  const [pickedLabel, setPickedLabel] = useState<string | null>(
    () => loadStoredSetup(instanceId)?.pickedLabel ?? null
  );
  const [favorable, setFavorable] = useState(() => loadStoredSetup(instanceId)?.favorable ?? "");

  // Persisted per instance, not globally , different instances have different
  // columns, so one instance's picks should never leak into another's.
  useEffect(() => {
    if (!instanceId || typeof window === "undefined") return;
    const payload: StoredSetup = { pickedFeatures, pickedLabel, favorable };
    try {
      localStorage.setItem(setupStorageKey(instanceId), JSON.stringify(payload));
    } catch {
      // Storage can be full or disabled (private browsing); the picks still
      // work for the rest of this session, they just won't survive a reload.
    }
  }, [instanceId, pickedFeatures, pickedLabel, favorable]);

  const setUseCase = useSelection((s) => s.setUseCase);
  const setInstance = useSelection((s) => s.setInstance);

  const instance = useQuery({
    queryKey: ["instance", instanceId],
    queryFn: () => api.get<InstanceDetail>(`/instances/${instanceId}`),
  });

  // Keep the sidebar's pickers pointing at whatever this page's URL says, so
  // a deep link or a browser Back stays consistent with what looks selected.
  useEffect(() => {
    if (instance.data) {
      setUseCase(usecaseId);
      setInstance(instance.data.id, instance.data.name);
    }
  }, [instance.data, usecaseId, setUseCase, setInstance]);

  const datasets = useQuery({
    queryKey: ["instance-datasets", instanceId],
    queryFn: () => api.get<DatasetFile[]>(`/instances/${instanceId}/datasets`),
  });

  const { data: jobs } = useJobs("instances", instanceId);
  const runJob = useRunJob("instances", instanceId);
  const byKind = latestByKind(jobs);
  useRefetchOnComplete(jobs, () => void instance.refetch(), seen);

  const columns = useMemo(
    () => Object.keys(datasets.data?.[0]?.csv_features ?? {}),
    [datasets.data]
  );
  const detected = useMemo(
    () => Object.keys(instance.data?.dataset_sensitive_features ?? {}),
    [instance.data]
  );
  // Columns the assessment could not compare anyway, so they never reach it.
  const ungroupable = useMemo(
    () => ungroupableColumns(datasets.data?.[0]?.csv_profile),
    [datasets.data]
  );

  const hasDataset = Boolean(datasets.data?.length);
  const label = pickedLabel ?? columns.find((column) => LABEL_GUESS.test(column)) ?? "";

  // Everything the picker offers except the column being predicted, and only
  // columns the dataset actually has , a detected feature can outlive the CSV
  // it was found in.
  const choices = columns.filter((column) => column !== label);
  // A blocked column is dropped even when the detector suggested it, so the
  // payload can never carry one.
  const selected = (pickedFeatures ?? detected).filter(
    (column) => choices.includes(column) && !ungroupable[column]
  );

  if (instance.isLoading) return <Skeleton className="h-72" />;
  if (instance.error || !instance.data) {
    return <ErrorState message="Could not load this instance." retry={() => void instance.refetch()} />;
  }

  function toggleFeature(column: string) {
    setPickedFeatures((current) => {
      const base = current ?? detected;
      return base.includes(column)
        ? base.filter((other) => other !== column)
        : [...base, column];
    });
  }

  const ready = Boolean(label) && Boolean(favorable.trim()) && selected.length > 0;
  const blockedReason = !hasDataset
    ? "Upload a CSV dataset on the instance first."
    : !label
      ? "Choose the target column above."
      : !favorable.trim()
        ? "Enter the value that counts as a favourable outcome."
        : !selected.length
          ? "Select at least one sensitive feature above."
          : undefined;

  return (
    <>
      <PageHeader
        title="Bias Analysis Setup"
        description="Choose the sensitive features and the outcome, then measure fairness across them."
      />

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Sensitive features</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 p-5 pt-0">
          <SensitiveFeaturePicker
            columns={choices}
            selected={selected}
            detected={detected}
            onToggle={toggleFeature}
            onUseDetected={
              pickedFeatures && detected.length ? () => setPickedFeatures(null) : undefined
            }
            ungroupable={ungroupable}
            disabled={!hasDataset}
          />

          {/* A helper, not a prerequisite: it suggests columns for the picker
              above, and the assessment runs with or without it. */}
          <div className="border-t">
            <AnalysisRow
              kind="sensitive_features"
              job={byKind.sensitive_features}
              description="Scores every column against the sensitive-attribute knowledge base and the model, and suggests what to select above."
              disabled={!hasDataset}
              disabledReason="Upload a CSV dataset on the instance first."
              onRun={() => runJob.mutate({ kind: "sensitive_features" })}
              running={runJob.isPending && runJob.variables?.kind === "sensitive_features"}
            />
          </div>
        </CardContent>
      </Card>

      {/* The detector's suggestions sit with the picker they feed, above the
          assessment that uses the selection. */}
      <div className="mb-6">
        <SensitiveFeatures features={instance.data.dataset_sensitive_features ?? {}} />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Bias assessment</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4 p-5 pt-0">
          <BiasTargetFields
            columns={columns}
            label={label}
            favorable={favorable}
            onLabelChange={(column) => {
              setPickedLabel(column);
              // The outcome cannot also be a feature measured against itself.
              setPickedFeatures((current) =>
                (current ?? detected).filter((other) => other !== column)
              );
            }}
            onFavorableChange={setFavorable}
          />

          <div className="border-t">
            <AnalysisRow
              kind="bias_assessment"
              job={byKind.bias_assessment}
              description={
                ready
                  ? `Measures statistical parity, disparate impact and performance disparity across ${selected.join(", ")}.`
                  : "Statistical parity, disparate impact and performance disparity, including intersections."
              }
              disabled={!ready}
              disabledReason={blockedReason}
              onRun={() =>
                runJob.mutate({
                  kind: "bias_assessment",
                  payload: {
                    label,
                    favorable_outcome: favorable.trim(),
                    sensitive_features: selected,
                  },
                })
              }
              running={runJob.isPending && runJob.variables?.kind === "bias_assessment"}
            >
              {byKind.bias_assessment?.status === "done" ? (
                <Button asChild size="sm" variant="outline">
                  <Link href={`/dashboard/use-cases/${usecaseId}/instances/${instanceId}/bias-analysis/report`}>
                    View report
                    <ArrowRight />
                  </Link>
                </Button>
              ) : null}
            </AnalysisRow>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
