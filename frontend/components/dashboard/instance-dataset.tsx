"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileSpreadsheet, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import type { DatasetFile } from "@/lib/types";
import { cn, formatBytes } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { Spinner } from "@/components/ui/primitives";

export function datasetQueryKey(instanceId: string) {
  return ["instance-datasets", instanceId];
}

/**
 * The one CSV an instance is about.
 *
 * An instance is a dataset to analyse, so every screen that shows an instance
 * shows this: the file it holds, or an invitation to upload one. Uploading over
 * an existing dataset replaces it , the analyses read the newest one, and two
 * source files sitting side by side only makes it ambiguous which.
 *
 * `row` is the compact form for a list; `card` is the full one, with the
 * columns the CSV was found to have.
 */
export function InstanceDataset({
  instanceId,
  ensureInstanceId,
  variant = "card",
  disabled = false,
}: {
  /** Null while a create dialog has not written the instance yet. */
  instanceId: string | null;
  /** Creates the instance on demand, for the create dialog. */
  ensureInstanceId?: () => Promise<string>;
  variant?: "card" | "row";
  disabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const datasets = useQuery({
    queryKey: datasetQueryKey(instanceId ?? "none"),
    queryFn: () => api.get<DatasetFile[]>(`/instances/${instanceId}/datasets`),
    enabled: Boolean(instanceId),
  });

  // Newest first, from the API's own ordering.
  const sources = (datasets.data ?? []).filter((file) => file.kind === "source");
  const current = sources[0];

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const id = instanceId ?? (await ensureInstanceId?.());
      if (!id) throw new Error("This instance does not exist yet.");

      const form = new FormData();
      form.append("file", file);
      form.append("kind", "source");
      const created = await api.upload<DatasetFile>(`/instances/${id}/datasets`, form);

      // Replace rather than pile up , but only once the new file is safely in,
      // so a rejected upload leaves the instance with the dataset it had.
      for (const stale of sources) {
        await api.delete(`/instances/${id}/datasets/${stale.id}`).catch(() => null);
      }
      return { id, created };
    },
    onSuccess: ({ id }) => {
      setError(null);
      toast.success(current ? "Dataset replaced." : "Dataset uploaded.");
      void queryClient.invalidateQueries({ queryKey: datasetQueryKey(id) });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      // `has_dataset` rides on the instance payloads, and the analyses are
      // gated on it , they have to hear that there is now something to run on.
      void queryClient.invalidateQueries({ queryKey: ["instance", id] });
      void queryClient.invalidateQueries({ queryKey: ["instances"] });
    },
    onError: (caught) => {
      // The API rejects an unreadable CSV with a field error naming the reason.
      const detail = caught instanceof ApiError ? caught.fieldErrors.file?.[0] : undefined;
      setError(detail ?? "Could not upload that dataset.");
    },
    onSettled: () => {
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`/instances/${instanceId}/datasets/${id}`),
    onSuccess: () => {
      toast.success("Dataset deleted.");
      void queryClient.invalidateQueries({ queryKey: datasetQueryKey(instanceId ?? "none") });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["instance", instanceId] });
      void queryClient.invalidateQueries({ queryKey: ["instances"] });
    },
    onError: () => toast.error("Could not delete that dataset."),
  });

  const busy = upload.isPending || remove.isPending;

  async function requestDelete(file: DatasetFile) {
    const ok = await confirm({
      title: `Delete ${file.filename}?`,
      description:
        "The instance is left with no data to analyse until another CSV is uploaded. Analyses already run keep their results.",
      confirmLabel: "Delete dataset",
      destructive: true,
    });
    if (ok) remove.mutate(file.id);
  }

  const picker = (
    <input
      ref={inputRef}
      type="file"
      accept=".csv,text/csv"
      className="sr-only"
      onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) upload.mutate(file);
      }}
    />
  );

  const uploadButton = (
    <Button
      type="button"
      size="sm"
      variant={current ? "outline" : "default"}
      className="relative z-10"
      disabled={disabled || busy}
      loading={upload.isPending}
      onClick={() => inputRef.current?.click()}
    >
      {!upload.isPending && <Upload />}
      {current ? "Replace" : "Upload CSV"}
    </Button>
  );

  if (variant === "row") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {datasets.isLoading ? (
          <Spinner className="text-muted-foreground" />
        ) : current ? (
          <>
            <FileSpreadsheet className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-xs">{current.filename}</span>
            <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
              {formatBytes(current.size)}
            </span>
          </>
        ) : (
          <span className="min-w-0 flex-1 text-xs text-amber-600">
            No dataset yet , there is nothing to analyse until one is uploaded.
          </span>
        )}

        {uploadButton}
        {current ? (
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="relative z-10 size-8 shrink-0"
            aria-label={`Delete ${current.filename}`}
            disabled={disabled || busy}
            loading={remove.isPending}
            onClick={() => void requestDelete(current)}
          >
            {!remove.isPending && <Trash2 className="size-4 text-muted-foreground" />}
          </Button>
        ) : null}
        {picker}

        {error ? (
          <p className="w-full text-xs text-destructive" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    );
  }

  const columns = Object.keys(current?.csv_features ?? {});

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium">Source dataset</p>
          <p className="text-xs text-muted-foreground">
            One CSV per instance. Its columns are read on upload, and every analysis runs
            against it.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {uploadButton}
          {current ? (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="relative z-10 size-8"
              aria-label={`Delete ${current.filename}`}
              disabled={disabled || busy}
              loading={remove.isPending}
              onClick={() => void requestDelete(current)}
            >
              {!remove.isPending && <Trash2 className="size-4 text-muted-foreground" />}
            </Button>
          ) : null}
        </div>
      </div>
      {picker}

      {error ? (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {datasets.isLoading ? (
        <Spinner className="text-muted-foreground" />
      ) : current ? (
        <div className="flex flex-col gap-2 rounded-md border p-3">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">
              {current.filename}
            </span>
            <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
              {formatBytes(current.size)}
            </span>
          </div>
          {columns.length ? (
            <div className="flex flex-col gap-1.5">
              <p className="text-xs text-muted-foreground">
                {columns.length} {columns.length === 1 ? "column" : "columns"}
              </p>
              <ul className="flex flex-wrap gap-1">
                {columns.map((column) => (
                  <li
                    key={column}
                    className={cn(
                      "max-w-full truncate rounded-md bg-muted px-2 py-0.5",
                      "font-mono text-[11px] text-muted-foreground"
                    )}
                    title={current.csv_features[column] || column}
                  >
                    {column}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-amber-600">
          No dataset yet. An instance without one cannot be analysed.
        </p>
      )}
    </div>
  );
}
