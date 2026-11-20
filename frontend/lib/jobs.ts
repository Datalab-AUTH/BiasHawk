"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import type { Job, JobKind } from "@/lib/types";

export const JOB_LABELS: Record<JobKind, string> = {
  rag_ingest: "Document ingestion",
  usecase_extract: "System documentation",
  instance_extract: "Data compliance form",
  data_governance: "Data governance",
  data_quality: "Data quality",
  sensitive_features: "Sensitive features",
  bias_assessment: "Bias assessment",
  bias_report: "Bias report",
  drift: "Drift analysis",
  risk_assessment: "Risk assessment",
};

const ACTIVE = new Set(["queued", "running"]);

export function isActive(job: Job | undefined) {
  return job !== undefined && ACTIVE.has(job.status);
}

/**
 * The most recent job of each kind for a scope.
 *
 * Polls only while something is actually running , an idle page makes no
 * requests at all.
 */
export function useJobs(scope: "instances" | "usecases", id: string | undefined) {
  return useQuery({
    queryKey: ["jobs", scope, id],
    enabled: Boolean(id),
    queryFn: () => api.get<Job[]>(`/${scope}/${id}/jobs`),
    refetchInterval: (query) => {
      const jobs = query.state.data;
      return jobs?.some((job) => ACTIVE.has(job.status)) ? 3000 : false;
    },
    // Analyses run for minutes, and people switch windows while they wait.
    // Without this React Query pauses the interval whenever the tab loses
    // focus, so they come back to a page still showing "Queued".
    refetchIntervalInBackground: true,
    // Coming back to the tab should also refresh immediately rather than
    // waiting out the remainder of the interval.
    refetchOnWindowFocus: true,
  });
}

/** Latest job per kind, so a screen can show the current state of each analysis. */
export function latestByKind(jobs: Job[] | undefined): Partial<Record<JobKind, Job>> {
  const latest: Partial<Record<JobKind, Job>> = {};
  for (const job of jobs ?? []) {
    // The API returns newest first, so the first of each kind wins.
    if (!latest[job.kind]) latest[job.kind] = job;
  }
  return latest;
}

export function useRunJob(scope: "instances" | "usecases", id: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ kind, payload }: { kind: JobKind; payload?: Record<string, unknown> }) =>
      api.post<Job>(`/${scope}/${id}/jobs`, { kind, ...(payload ? { payload } : {}) }),
    onSuccess: (job) => {
      toast.success(`${JOB_LABELS[job.kind]} queued.`);
      void queryClient.invalidateQueries({ queryKey: ["jobs", scope, id] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const kindErrors = error.fieldErrors.kind;
        toast.error(kindErrors?.[0] ?? error.message);
      } else {
        toast.error("Could not start that analysis.");
      }
    },
  });
}

/**
 * Refresh the underlying record when a job finishes, so results appear without
 * the user reloading.
 */
export function useRefetchOnComplete(
  jobs: Job[] | undefined,
  onComplete: () => void,
  seen: React.MutableRefObject<Set<string>>
) {
  for (const job of jobs ?? []) {
    if (job.status === "done" && !seen.current.has(job.id)) {
      seen.current.add(job.id);
      // Defer so this never runs during render.
      queueMicrotask(onComplete);
    }
  }
}
