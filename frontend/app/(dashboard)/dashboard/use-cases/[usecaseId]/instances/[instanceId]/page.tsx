"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ChartLine, ChevronLeft, Columns3Cog, FileChartPie, FileWarning, Grid2x2Check, Pencil } from "lucide-react";

import { api } from "@/lib/api";
import { latestByKind, useJobs, useRefetchOnComplete } from "@/lib/jobs";
import { useSelection } from "@/lib/store";
import type { AIDataComplianceForm, InstanceDetail } from "@/lib/types";
import { JobBadge, PipelineStatus } from "@/components/dashboard/job-status";
import { InstanceDataset } from "@/components/dashboard/instance-dataset";
import { DataComplianceForm } from "@/components/dashboard/system-documentation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CreateInstanceDialog } from "@/components/dashboard/create-instance-dialog";
import { ErrorState, PageHeader } from "@/components/ui/primitives";
import { Skeleton } from "@/components/ui/skeleton";

const ANALYSES = [
  { slug: "data-gov", label: "Data Governance", icon: Columns3Cog, kind: "data_governance" },
  { slug: "data-quality", label: "Data Quality", icon: Grid2x2Check, kind: "data_quality" },
  { slug: "bias-analysis/setup", label: "Bias Analysis", icon: FileChartPie, kind: "bias_assessment" },
  { slug: "bias-drift", label: "Bias Drift", icon: ChartLine, kind: "drift" },
  { slug: "risk-assessment", label: "Risk Assessment", icon: FileWarning, kind: "risk_assessment" },
] as const;

export default function InstanceOverviewPage() {
  const { usecaseId, instanceId } = useParams<{ usecaseId: string; instanceId: string }>();
  const seen = useRef(new Set<string>());
  const [editing, setEditing] = useState(false);
  const setUseCase = useSelection((s) => s.setUseCase);
  const setInstance = useSelection((s) => s.setInstance);

  const instance = useQuery({
    queryKey: ["instance", instanceId],
    queryFn: () => api.get<InstanceDetail>(`/instances/${instanceId}`),
  });

  // Opening an instance selects it, so the sidebar follows the URL , not just
  // the instance but its use case too, otherwise a deep link or a Back into a
  // different use case's instance leaves the "Instance" picker fetching the
  // wrong use case's list and rendering as unselected.
  useEffect(() => {
    if (instance.data) {
      setUseCase(usecaseId);
      setInstance(instance.data.id, instance.data.name);
    }
  }, [instance.data, usecaseId, setUseCase, setInstance]);

  const { data: jobs } = useJobs("instances", instanceId);
  const byKind = latestByKind(jobs);
  useRefetchOnComplete(jobs, () => void instance.refetch(), seen);

  if (instance.isLoading) return <Skeleton className="h-72" />;
  if (instance.error || !instance.data) {
    return <ErrorState message="Could not load this instance." retry={() => void instance.refetch()} />;
  }

  const data = instance.data;
  const hasForm = "Data_Overview" in (data.metadata ?? {});

  return (
    <>
      <PageHeader
        title={data.name}
        description={data.description || undefined}
        breadcrumb={
          <Link
            href={`/dashboard/use-cases/${usecaseId}`}
            className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="size-4" aria-hidden />
            Back to use case
          </Link>
        }
      />

      <CreateInstanceDialog
        usecaseId={usecaseId}
        editing={data}
        open={editing}
        onOpenChange={(next) => {
          setEditing(next);
          if (!next) void instance.refetch();
        }}
      />

      <div className="flex flex-col gap-6">
        {/* The dataset is what the instance is, and every analysis below reads
            it , so it comes first rather than sitting off to one side. */}
        <Card>
          <CardHeader>
            <CardTitle>Dataset</CardTitle>
          </CardHeader>
          <CardContent>
            <InstanceDataset instanceId={instanceId} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Analyses</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col">
              {ANALYSES.map(({ slug, label, icon: Icon, kind }) => (
                <li key={slug} className="border-b py-3 last:border-b-0">
                  <Link
                    href={`/dashboard/use-cases/${usecaseId}/instances/${instanceId}/${slug}`}
                    className="flex items-center gap-3 rounded-md px-1 py-1 hover:bg-accent"
                  >
                    <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="flex-1 font-medium">{label}</span>
                    <JobBadge job={byKind[kind]} />
                  </Link>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <DataComplianceForm
          data={hasForm ? (data.metadata as AIDataComplianceForm) : null}
          actions={
            <>
              <PipelineStatus ingest={byKind.rag_ingest} extract={byKind.instance_extract} />
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                <Pencil />
                Edit details
              </Button>
            </>
          }
        />
      </div>
    </>
  );
}
