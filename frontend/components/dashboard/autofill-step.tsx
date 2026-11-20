"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, TriangleAlert, Upload } from "lucide-react";

import { ApiError, api } from "@/lib/api";
import type { DataFile, Job } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { FileUpload } from "@/components/dashboard/file-upload";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/primitives";

export type AutofillPhase =
  | "idle"
  | "uploading"
  | "ingesting"
  | "extracting"
  | "done"
  | "error";

export const AUTOFILL_PHASE_TEXT: Record<AutofillPhase, string> = {
  idle: "",
  uploading: "Uploading the document…",
  ingesting: "Indexing the document…",
  extracting: "Reading it and filling in the details…",
  done: "Details filled in. Review them on the next steps.",
  error: "",
};

function failureReason(job: Job) {
  return (job.error.trim().split("\n").pop() ?? "The job failed.").slice(0, 300);
}

/**
 * Follow the pipeline the upload started.
 *
 * Uploading a document enqueues ingestion server-side, and ingestion chains
 * into extraction when it finishes , so there is nothing to trigger here, only
 * progress to report.
 */
async function followPipeline(
  scope: "usecases" | "instances",
  scopeId: string,
  extractKind: string,
  onPhase: (phase: AutofillPhase) => void,
  signal: { cancelled: boolean }
): Promise<void> {
  for (let attempt = 0; attempt < 220; attempt++) {
    if (signal.cancelled) throw new Error("cancelled");

    const jobs = await api.get<Job[]>(`/${scope}/${scopeId}/jobs`);
    const latest = (kind: string) => jobs.find((job) => job.kind === kind);
    const extract = latest(extractKind);
    const ingest = latest("rag_ingest");

    if (extract?.status === "done") return;
    if (extract?.status === "failed") throw new Error(failureReason(extract));
    if (ingest?.status === "failed") throw new Error(failureReason(ingest));

    onPhase(extract || ingest?.status === "done" ? "extracting" : "ingesting");
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  throw new Error("Timed out waiting for the document to be processed.");
}

export type AutofillRun = {
  phase: AutofillPhase;
  error: string | null;
  /** True from the upload until the extraction finishes or fails. */
  busy: boolean;
  start: (file: File) => void;
  reset: () => void;
};

/**
 * The upload-and-extract run behind step 0.
 *
 * It lives in the dialog rather than in `AutofillStep` on purpose: the dialog
 * can be minimised while a document is being read, which unmounts the step.
 * Holding the progress here means reopening shows the run where it actually
 * is, instead of an idle step with the form still locked behind it.
 */
export function useAutofillRun({
  scope,
  ensureScopeId,
  extractKind,
  onExtracted,
}: {
  scope: "usecases" | "instances";
  /**
   * Creates the record on demand and returns its id. Uploading is the only
   * thing that needs one before Finish, so nothing is written to the database
   * until the user actually uploads something.
   */
  ensureScopeId: () => Promise<string>;
  extractKind: "usecase_extract" | "instance_extract";
  /**
   * Called with the id of the record that was filled in. The id is passed
   * rather than read from the caller's state because this callback was
   * captured before the record existed , its copy of that state is null.
   */
  onExtracted: (scopeId: string) => void;
}): AutofillRun {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<AutofillPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const cancelled = useRef({ cancelled: false });

  const filesQueryKey = scope === "usecases" ? "usecase-files" : "instance-files";

  async function run(file: File) {
    setError(null);
    cancelled.current = { cancelled: false };

    try {
      setPhase("uploading");
      const scopeId = await ensureScopeId();
      const form = new FormData();
      form.append("file", file);
      await api.upload(`/${scope}/${scopeId}/files`, form);

      // The list in the step mounted the moment the record was created, which
      // is before this upload finished , so it is holding an empty result. The
      // jobs query is stale for the same reason: ingestion has just started.
      void queryClient.invalidateQueries({ queryKey: [filesQueryKey, scopeId] });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });

      // The upload already started ingestion, which chains into extraction.
      setPhase("ingesting");
      await followPipeline(scope, scopeId, extractKind, setPhase, cancelled.current);

      setPhase("done");
      onExtracted(scopeId);
    } catch (caught) {
      if (caught instanceof Error && caught.message === "cancelled") return;
      setPhase("error");
      setError(
        caught instanceof ApiError
          ? (caught.fieldErrors.file?.[0] ?? caught.message)
          : caught instanceof Error
            ? caught.message
            : "Could not read that document."
      );
    }
  }

  return {
    phase,
    error,
    busy: phase === "uploading" || phase === "ingesting" || phase === "extracting",
    start: (file) => void run(file),
    reset: () => {
      setPhase("idle");
      setError(null);
    },
  };
}

/**
 * The bar a minimised create dialog leaves behind.
 *
 * Out of the way but not gone: the read carries on, this says where it got to,
 * and the button brings the dialog back.
 */
export function MinimisedRun({
  run,
  title,
  onReopen,
}: {
  run: AutofillRun;
  title: string;
  onReopen: () => void;
}) {
  const failed = run.phase === "error";
  return (
    // Top right, not bottom: the toasts live in the bottom corner, and one of
    // them lands the moment this run finishes.
    <div
      role="status"
      className="fixed right-4 top-20 z-40 flex w-[min(24rem,calc(100vw-2rem))] items-start gap-3 rounded-lg border bg-background p-4 shadow-lg"
    >
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm font-medium">
          {run.busy ? (
            <Spinner />
          ) : failed ? (
            <TriangleAlert className="size-4 shrink-0 text-destructive" aria-hidden />
          ) : (
            <CheckCircle2 className="size-4 shrink-0 text-emerald-600" aria-hidden />
          )}
          <span className="truncate">{title}</span>
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {failed ? (run.error ?? "Could not read that document.") : AUTOFILL_PHASE_TEXT[run.phase]}
        </p>
      </div>
      <Button
        type="button"
        size="sm"
        variant={run.busy ? "outline" : "default"}
        className="shrink-0"
        onClick={onReopen}
      >
        {run.busy ? "Reopen" : "Review"}
      </Button>
    </div>
  );
}

/**
 * Step 0 of the create forms.
 *
 * Upload a document and the record is filled in from it; skip and the following
 * steps are typed by hand. Either way the record ends up in the same shape.
 */
export function AutofillStep({
  run,
  scope,
  scopeId,
  accept = ".pdf,.docx,.txt,.md",
}: {
  /** The run this step drives and reports on; owned by the dialog. */
  run: AutofillRun;
  scope: "usecases" | "instances";
  /** The record's id once it exists; null while creating from scratch. */
  scopeId: string | null;
  accept?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const filesQueryKey = scope === "usecases" ? "usecase-files" : "instance-files";
  const busy = run.busy;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          Do you want the details filled in automatically from your documents?
        </CardTitle>
        <CardDescription>
          Upload a PDF, Word document, text or Markdown file describing the system. It is read
          and used to fill in the following steps, which you can then review and correct. To
          type everything yourself instead, continue without uploading.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            onClick={() => inputRef.current?.click()}
            loading={busy}
            disabled={busy}
          >
            {!busy && <Upload />}
            Upload a document
          </Button>

          {run.phase === "done" ? (
            <span className="inline-flex items-center gap-2 text-sm text-emerald-600">
              <CheckCircle2 className="size-4" aria-hidden />
              {AUTOFILL_PHASE_TEXT.done}
            </span>
          ) : busy ? (
            <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner />
              {AUTOFILL_PHASE_TEXT[run.phase]}
            </span>
          ) : null}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Clear it here rather than when the run ends: minimising unmounts
            // this input, and picking the same file twice has to still fire.
            event.target.value = "";
            if (file) run.start(file);
          }}
        />

        {run.error ? (
          <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
            {run.error}
          </p>
        ) : null}

        {busy ? (
          <p className="text-xs text-muted-foreground">
            This takes about half a minute. You can leave this open , it keeps working. Minimise
            it and it keeps working too.
          </p>
        ) : null}

        {scopeId ? (
          <div className="border-t pt-4">
            <FileUpload<DataFile>
              endpoint={`/${scope}/${scopeId}/files`}
              queryKey={[filesQueryKey, scopeId]}
              accept={accept}
              label="Attached documents"
              hint="Adding one re-reads the details; removing one re-reads what is left."
              noun="document"
              disabled={busy}
            />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
