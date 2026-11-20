"use client";

import { useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { latestByKind, useJobs, useRefetchOnComplete, useRunJob } from "@/lib/jobs";
import { useSelection } from "@/lib/store";
import type { DatasetFile, InstanceDetail, JobKind } from "@/lib/types";
import { AnalysisRow } from "@/components/dashboard/job-status";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState, PageHeader } from "@/components/ui/primitives";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The shape every analysis screen shares: a header, the run control for that
 * analysis, and whatever the analysis produced.
 *
 * Keeping this in one place is why Data Governance, Data Quality, Bias Drift
 * and Risk Assessment are ~40 lines each instead of repeating the same
 * fetch-poll-render scaffolding five times.
 */
export function AnalysisPage({
  kind,
  title,
  description,
  runDescription,
  requires,
  requiresLabel,
  requiresDataset = false,
  children,
  onRun,
  extraControls,
}: {
  kind: JobKind;
  title: string;
  description?: string;
  runDescription?: string;
  /** Predicate over the instance, e.g. "has a dataset". */
  requires?: (instance: InstanceDetail) => boolean;
  requiresLabel?: string;
  /**
   * Blocks the run until the instance has a source CSV.
   *
   * Read from the datasets endpoint rather than from a flag on the instance,
   * so the check does not depend on which build of the API is serving.
   */
  requiresDataset?: boolean;
  children: (instance: InstanceDetail) => React.ReactNode;
  onRun?: () => void;
  extraControls?: (instance: InstanceDetail) => React.ReactNode;
}) {
  const { usecaseId, instanceId } = useParams<{ usecaseId: string; instanceId: string }>();
  const seen = useRef(new Set<string>());
  const setUseCase = useSelection((s) => s.setUseCase);
  const setInstance = useSelection((s) => s.setInstance);
  const useCaseName = useSelection((s) => s.selectedUseCaseName);

  const instance = useQuery({
    queryKey: ["instance", instanceId],
    queryFn: async () => {
      const data = await api.get<InstanceDetail>(`/instances/${instanceId}`);
      // Keep the sidebar's contextual links pointing at whatever the URL says,
      // so a deep link or a browser Back stays consistent with the selection.
      // The use case has to be set first: setUseCase resets the instance
      // whenever the id actually changes, so setting it after would wipe the
      // instance this same call is about to set.
      setUseCase(usecaseId);
      setInstance(data.id, data.name);
      return data;
    },
  });

  const datasets = useQuery({
    queryKey: ["instance-datasets", instanceId],
    queryFn: () => api.get<DatasetFile[]>(`/instances/${instanceId}/datasets`),
    enabled: requiresDataset,
  });

  const { data: jobs } = useJobs("instances", instanceId);
  const runJob = useRunJob("instances", instanceId);
  const job = latestByKind(jobs)[kind];
  useRefetchOnComplete(jobs, () => void instance.refetch(), seen);

  if (instance.isLoading) return <Skeleton className="h-72" />;
  if (instance.error || !instance.data) {
    return (
      <ErrorState message="Could not load this instance." retry={() => void instance.refetch()} />
    );
  }

  const data = instance.data;
  const hasDataset = (datasets.data ?? []).some((file) => file.kind === "source");
  const unmet = requires ? !requires(data) : false;
  // Blocked while the datasets are still loading too, so a fast click cannot
  // enqueue a job that the worker would only fail on. The reason waits until
  // there is an answer to give, rather than accusing the user mid-fetch.
  const blocked = unmet || (requiresDataset && !hasDataset);
  const blockedReason = unmet
    ? requiresLabel
    : requiresDataset && !hasDataset && !datasets.isLoading
      ? "Upload this instance's CSV dataset before running it, there is nothing to analyse without one."
      : undefined;

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        breadcrumb={
          <nav
            aria-label="Breadcrumb"
            className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground"
          >
            <Link href="/dashboard/use-cases" className="hover:text-foreground">
              Project Setup
            </Link>
            <ChevronRight className="size-3.5" aria-hidden />
            <Link href={`/dashboard/use-cases/${usecaseId}`} className="hover:text-foreground">
              {useCaseName ?? "Use case"}
            </Link>
            <ChevronRight className="size-3.5" aria-hidden />
            <Link
              href={`/dashboard/use-cases/${usecaseId}/instances/${instanceId}`}
              className="hover:text-foreground"
            >
              {data.name}
            </Link>
            <ChevronRight className="size-3.5" aria-hidden />
            <span className="font-medium text-foreground">{title}</span>
          </nav>
        }
      />

      <Card className="mb-6">
        <CardContent className="p-5">
          <AnalysisRow
            kind={kind}
            job={job}
            description={runDescription}
            disabled={blocked}
            disabledReason={blockedReason}
            onRun={onRun ?? (() => runJob.mutate({ kind }))}
            running={runJob.isPending}
          >
            {extraControls?.(data)}
          </AnalysisRow>
        </CardContent>
      </Card>

      {children(data)}
    </>
  );
}
