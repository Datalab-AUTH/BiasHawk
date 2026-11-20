"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import type { DataFile, DatasetFile } from "@/lib/types";
import { formatBytes } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { Spinner } from "@/components/ui/primitives";

type Props = {
  /** e.g. "/usecases/<id>/files" or "/instances/<id>/datasets" */
  endpoint: string;
  queryKey: unknown[];
  accept: string;
  label: string;
  hint: string;
  /** Datasets need a `kind`; documents do not. */
  extraFields?: Record<string, string>;
  /** Shown on the confirm prompt, e.g. "document" or "dataset". */
  noun?: string;
  /** Blocks uploads and deletes, e.g. while a document is being read. */
  disabled?: boolean;
};

export function FileUpload<T extends DataFile | DatasetFile>({
  endpoint,
  queryKey,
  accept,
  label,
  hint,
  extraFields,
  noun = "file",
  disabled = false,
}: Props) {
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => api.get<T[]>(endpoint),
  });

  /**
   * Uploading and deleting both start an ingestion job server-side, so the
   * job queries have to be refreshed too , otherwise the pipeline badge and
   * the sidebar keep showing the state from before the upload until something
   * else happens to refetch them.
   */
  function refreshAfterChange() {
    void queryClient.invalidateQueries({ queryKey });
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
  }

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      for (const [key, value] of Object.entries(extraFields ?? {})) form.append(key, value);
      return api.upload<T>(endpoint, form);
    },
    onSuccess: () => {
      toast.success("File uploaded.");
      setError(null);
      refreshAfterChange();
    },
    onError: (caught) => {
      // The API rejects unreadable CSVs and unsupported document types with a
      // field error naming the reason; show that rather than a generic failure.
      const detail = caught instanceof ApiError ? caught.fieldErrors.file?.[0] : undefined;
      setError(detail ?? "Could not upload that file.");
    },
    onSettled: () => {
      if (inputRef.current) inputRef.current.value = "";
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.delete(`${endpoint}/${id}`),
    onSuccess: () => {
      toast.success("File deleted.");
      refreshAfterChange();
    },
    onError: () => toast.error("Could not delete that file."),
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          loading={upload.isPending}
          disabled={disabled}
        >
          {!upload.isPending && <Upload />}
          Upload
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) upload.mutate(file);
          }}
        />
      </div>

      {error ? (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      {isLoading ? (
        <Spinner className="text-muted-foreground" />
      ) : data?.length ? (
        <ul className="flex flex-col gap-1.5">
          {data.map((file) => {
            const deleting = remove.isPending && remove.variables === file.id;
            return (
              <li
                key={file.id}
                className="flex items-center gap-2 rounded-md bg-muted/60 px-3 py-2 text-sm"
              >
                <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                <span className="min-w-0 flex-1 truncate">{file.filename}</span>
                <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                  {formatBytes(file.size)}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0"
                  aria-label={`Delete ${file.filename}`}
                  loading={deleting}
                  disabled={disabled}
                  onClick={async () => {
                    const ok = await confirm({
                      title: `Delete ${file.filename}?`,
                      description: `The ${noun} is removed and what was read from it is re-read from whatever is left.`,
                      confirmLabel: "Delete",
                      destructive: true,
                    });
                    if (ok) remove.mutate(file.id);
                  }}
                >
                  {!deleting && <Trash2 className="size-4 text-muted-foreground" />}
                </Button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
          No {noun}s uploaded yet.
        </p>
      )}
    </div>
  );
}
