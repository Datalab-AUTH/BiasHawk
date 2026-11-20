"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronLeft, Database, Pencil, Plus } from "lucide-react";

import { api } from "@/lib/api";
import { latestByKind, useJobs, useRefetchOnComplete } from "@/lib/jobs";
import { useIsAutofilling, useSelection } from "@/lib/store";
import type { AISystemDocumentation, DataFile, Instance, Usecase } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";
import { PipelineStatus } from "@/components/dashboard/job-status";
import { InstanceDataset } from "@/components/dashboard/instance-dataset";
import { SystemDocumentation } from "@/components/dashboard/system-documentation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader } from "@/components/ui/primitives";
import { CreateInstanceDialog } from "@/components/dashboard/create-instance-dialog";
import { CreateUsecaseDialog } from "@/components/dashboard/create-usecase-dialog";
import { Skeleton } from "@/components/ui/skeleton";

export default function UsecaseDetailPage() {
  const { usecaseId } = useParams<{ usecaseId: string }>();
  const queryClient = useQueryClient();
  const seen = useRef(new Set<string>());
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState(false);

  const setUseCase = useSelection((s) => s.setUseCase);
  const setInstance = useSelection((s) => s.setInstance);
  const selectedInstanceId = useSelection((s) => s.selectedInstanceId);

  const usecase = useQuery({
    queryKey: ["usecase", usecaseId],
    queryFn: () => api.get<Usecase>(`/usecases/${usecaseId}`),
  });

  // Opening a use case selects it, so the sidebar follows the URL.
  useEffect(() => {
    if (usecase.data) setUseCase(usecase.data.id, usecase.data.name);
  }, [usecase.data, setUseCase]);

  const instances = useQuery({
    queryKey: ["instances", usecaseId],
    queryFn: () => api.get<Instance[]>(`/instances?usecase=${usecaseId}`),
  });

  const documents = useQuery({
    queryKey: ["usecase-files", usecaseId],
    queryFn: () => api.get<DataFile[]>(`/usecases/${usecaseId}/files`),
  });

  // A minimised create/edit dialog may still be filling this use case in from
  // a document. Editing it now would be overwritten when the extraction lands.
  const autofilling = useIsAutofilling(usecaseId);

  const { data: jobs } = useJobs("usecases", usecaseId);
  const byKind = latestByKind(jobs);
  useRefetchOnComplete(jobs, () => void usecase.refetch(), seen);

  if (usecase.isLoading) return <Skeleton className="h-64" />;
  if (usecase.error || !usecase.data) {
    return <ErrorState message="Could not load this use case." retry={() => void usecase.refetch()} />;
  }

  const metadata = usecase.data.metadata as AISystemDocumentation | Record<string, never>;
  const hasMetadata = "general_information" in metadata;
  const hasDocuments = Boolean(documents.data?.length);

  return (
    <>
      <PageHeader
        title={usecase.data.name}
        description={usecase.data.description || undefined}
        breadcrumb={
          <Link
            href="/dashboard/use-cases"
            className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="size-4" aria-hidden />
            Project Setup
          </Link>
        }
      />

      <CreateUsecaseDialog
        open={editing}
        editing={usecase.data}
        onOpenChange={(next) => {
          setEditing(next);
          if (!next) void usecase.refetch();
        }}
      />

      <CreateInstanceDialog
        usecaseId={usecaseId}
        open={adding}
        onOpenChange={(next) => {
          setAdding(next);
          if (!next) {
            void queryClient.invalidateQueries({ queryKey: ["instances", usecaseId] });
            void usecase.refetch();
          }
        }}
      />

      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-6">

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Instances</CardTitle>
              <Button size="sm" variant="outline" onClick={() => setAdding((v) => !v)}>
                <Plus />
                New instance
              </Button>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">

              {instances.isLoading ? (
                <Skeleton className="h-20" />
              ) : !instances.data?.length ? (
                <EmptyState
                  icon={Database}
                  title="No instances yet"
                  description="An instance is one dataset to analyse , a snapshot in time, or a version to compare against another."
                />
              ) : (
                <ul className="flex flex-col gap-2">
                  {instances.data.map((instance) => (
                    <li
                      key={instance.id}
                      className={cn(
                        "relative flex flex-col gap-2 rounded-md border px-4 py-3 transition-colors",
                        // The selected instance is the one the sidebar's
                        // analyses point at, so say which that is plainly.
                        instance.id === selectedInstanceId
                          ? "border-primary/50 bg-accent/50 ring-1 ring-primary/25"
                          : "hover:border-foreground/30 hover:bg-accent/30"
                      )}
                    >
                      <Link
                        href={`/dashboard/use-cases/${usecaseId}/instances/${instance.id}`}
                        onClick={() => setInstance(instance.id, instance.name)}
                        // Stretched over the whole row, so anywhere on it opens
                        // the instance. The dataset controls below sit above
                        // this overlay and keep their own clicks.
                        className="flex items-center justify-between gap-3 after:absolute after:inset-0 after:content-['']"
                      >
                        <div className="min-w-0">
                          <p className="flex flex-wrap items-center gap-2 font-medium">
                            <span className="truncate">{instance.name}</span>
                            {instance.id === selectedInstanceId ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                                <Check className="size-3" aria-hidden />
                                Selected
                              </span>
                            ) : null}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Created {formatDate(instance.created_at)}
                          </p>
                        </div>
                      </Link>
                      {/* An instance is a dataset to analyse, so the dataset it
                          holds , or the lack of one , belongs on this row. */}
                      <div className="border-t pt-2">
                        <InstanceDataset instanceId={instance.id} variant="row" />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <SystemDocumentation
            data={hasMetadata ? (metadata as AISystemDocumentation) : null}
            actions={
              <>
                <PipelineStatus ingest={byKind.rag_ingest} extract={byKind.usecase_extract} />
                <Button
                  size="sm"
                  variant="outline"
                  disabled={autofilling}
                  title={
                    autofilling ? "A document is being read into this use case." : undefined
                  }
                  onClick={() => setEditing(true)}
                >
                  <Pencil />
                  Edit details
                </Button>
              </>
            }
          />
        </div>

      </div>
    </>
  );
}

