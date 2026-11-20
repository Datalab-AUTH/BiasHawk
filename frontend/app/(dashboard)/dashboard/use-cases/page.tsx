"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, FolderKanban, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useAutofillLocks, useSelection } from "@/lib/store";
import type { Usecase } from "@/lib/types";
import { cn, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui/primitives";
import { CreateUsecaseDialog } from "@/components/dashboard/create-usecase-dialog";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Project Setup , the list of use cases.
 *
 * Instances belong to a use case, so they are listed on that use case's own
 * page rather than duplicated here. Switching between them once they exist is
 * the sidebar's job.
 */
export default function ProjectSetupPage() {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const [creating, setCreating] = useState(false);

  const useCaseId = useSelection((s) => s.selectedUseCaseId);
  const setUseCase = useSelection((s) => s.setUseCase);
  // Use cases a minimised create/edit dialog is still filling in from a
  // document. Touching one now races the extraction that is writing to it.
  const busyIds = useAutofillLocks((s) => s.locked);

  const usecases = useQuery({
    queryKey: ["usecases"],
    queryFn: () => api.get<Usecase[]>("/usecases"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/usecases/${id}`),
    onSuccess: (_data, id) => {
      toast.success("Use case deleted.");
      if (id === useCaseId) setUseCase(null);
      void queryClient.invalidateQueries({ queryKey: ["usecases"] });
    },
    onError: () => toast.error("Could not delete that use case."),
  });

  return (
    <>
      <PageHeader
        title="Project Setup"
        description="Pick the use case to work on, or create a new one. Open it to manage its instances."
        actions={
          <Button onClick={() => setCreating((open) => !open)}>
            <Plus />
            New use case
          </Button>
        }
      />

      <CreateUsecaseDialog open={creating} onOpenChange={setCreating} />

      {usecases.isLoading ? (
        <Skeleton className="h-28" />
      ) : usecases.error ? (
        <ErrorState message="Could not load your use cases." retry={() => void usecases.refetch()} />
      ) : !usecases.data?.length ? (
        <EmptyState
          icon={FolderKanban}
          title="No use cases yet"
          description="Create one to start assessing an AI system."
          action={<Button onClick={() => setCreating(true)}>New use case</Button>}
        />
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {usecases.data.map((usecase) => {
            const selected = usecase.id === useCaseId;
            const autofilling = busyIds.includes(usecase.id);
            return (
              <li key={usecase.id}>
                <Card
                  className={cn(
                    "relative h-full overflow-hidden transition-colors",
                    // The selected one carries the sidebar's analyses, so it has
                    // to be obvious at a glance which one that is.
                    selected
                      ? "border-primary/50 bg-accent/50 ring-1 ring-primary/25"
                      : "hover:border-foreground/30 hover:bg-accent/30"
                  )}
                >
                  <CardContent className="flex items-start gap-3 p-4">
                    {/* One click both selects the use case and opens it ,
                        selecting without going in was a step for its own sake. */}
                    <Link
                      href={`/dashboard/use-cases/${usecase.id}`}
                      onClick={() => setUseCase(usecase.id, usecase.name)}
                      aria-current={selected ? "true" : undefined}
                      // The link stretches over the whole card, so anywhere on
                      // it opens the use case. The controls beside it sit above
                      // that overlay and keep their own clicks.
                      className="min-w-0 flex-1 text-left after:absolute after:inset-0 after:content-['']"
                    >
                      <span className="flex flex-wrap items-center gap-2 font-medium">
                        {usecase.name}
                        {selected ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                            <Check className="size-3" aria-hidden />
                            Selected
                          </span>
                        ) : null}
                      </span>
                      {usecase.description ? (
                        <span className="mt-0.5 line-clamp-2 block text-sm text-muted-foreground">
                          {usecase.description}
                        </span>
                      ) : null}
                      <span className="mt-1.5 block text-xs text-muted-foreground">
                        {usecase.instance_count}{" "}
                        {usecase.instance_count === 1 ? "instance" : "instances"} · created{" "}
                        {formatDate(usecase.created_at)}
                      </span>
                      {autofilling ? (
                        <span className="mt-1.5 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
                          <Spinner className="size-3" />
                          Reading your document , locked until it finishes.
                        </span>
                      ) : null}
                    </Link>

                    <div className="relative z-10 flex shrink-0 items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${usecase.name}`}
                        disabled={autofilling}
                        title={autofilling ? "A document is being read into this use case." : undefined}
                        onClick={async () => {
                          const ok = await confirm({
                            title: `Delete "${usecase.name}"?`,
                            description:
                              "Its instances, documents and analyses go with it. This cannot be undone.",
                            confirmLabel: "Delete use case",
                            destructive: true,
                          });
                          if (ok) remove.mutate(usecase.id);
                        }}
                      >
                        <Trash2 className="size-4 text-muted-foreground" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
