"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { latestByKind, useJobs, useRefetchOnComplete, useRunJob } from "@/lib/jobs";
import type { DriftRecord, Instance, InstanceDetail } from "@/lib/types";
import { AnalysisRow } from "@/components/dashboard/job-status";
import { DriftSummary } from "@/components/dashboard/drift-summary";
import { ReportView } from "@/components/dashboard/report-view";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState, Field, PageHeader } from "@/components/ui/primitives";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

export default function BiasDriftPage() {
  const { usecaseId, instanceId } = useParams<{ usecaseId: string; instanceId: string }>();
  const seen = useRef(new Set<string>());
  const [baseline, setBaseline] = useState("");

  const instance = useQuery({
    queryKey: ["instance", instanceId],
    queryFn: () => api.get<InstanceDetail>(`/instances/${instanceId}`),
  });

  const siblings = useQuery({
    queryKey: ["instances", usecaseId],
    queryFn: () => api.get<Instance[]>(`/instances?usecase=${usecaseId}`),
  });

  const drift = useQuery({
    queryKey: ["drift", instanceId],
    queryFn: () => api.get<DriftRecord[]>(`/instances/${instanceId}/drift`),
  });

  const { data: jobs } = useJobs("instances", instanceId);
  const runJob = useRunJob("instances", instanceId);
  const job = latestByKind(jobs).drift;
  useRefetchOnComplete(jobs, () => {
    void instance.refetch();
    void drift.refetch();
  }, seen);

  const options = (siblings.data ?? []).filter((i) => i.id !== instanceId);
  useEffect(() => {
    if (!baseline && options.length) setBaseline(options[0].id);
  }, [options, baseline]);

  if (instance.isLoading) return <Skeleton className="h-72" />;
  if (instance.error) {
    return <ErrorState message="Could not load this instance." retry={() => void instance.refetch()} />;
  }

  const record = drift.data?.find((d) => d.initial_instance === baseline) ?? drift.data?.[0];

  return (
    <>
      <PageHeader
        title="Bias Drift"
        description="Compare this instance against an earlier one: distribution drift in the data, and drift in the fairness metrics."
      />

      <Card className="mb-6">
        <CardContent className="flex flex-col gap-4 p-5">
          <Field
            label="Compare against"
            htmlFor="baseline"
            hint="The earlier instance to treat as the baseline."
          >
            <Select value={baseline || undefined} onValueChange={setBaseline} disabled={!options.length}>
              <SelectTrigger id="baseline" className="w-full max-w-sm">
                <SelectValue
                  placeholder={
                    options.length ? "Select an instance" : "No other instance in this use case"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {options.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    {option.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>

          <AnalysisRow
            kind="drift"
            job={job}
            description="Kolmogorov-Smirnov, PSI and Jensen-Shannon on the data; disparity changes on the fairness metrics."
            disabled={!baseline}
            disabledReason="Create a second instance in this use case to compare against."
            onRun={() => runJob.mutate({ kind: "drift", payload: { initial_instance: baseline } })}
            running={runJob.isPending}
          />
        </CardContent>
      </Card>

      {record ? (
        <div className="flex flex-col gap-6">
          <DriftSummary record={record} />
          <ReportView
            markdown={record.final_drift_report}
            pdfPath={`/drift/${record.id}/pdf`}
            emptyTitle="No drift report yet"
          />
        </div>
      ) : (
        <ReportView
          markdown=""
          emptyTitle="No drift comparison yet"
          emptyDescription="Pick a baseline instance and run the analysis."
        />
      )}
    </>
  );
}
