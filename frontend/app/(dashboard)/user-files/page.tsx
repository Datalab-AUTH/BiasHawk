"use client";

import Link from "next/link";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Download, FileText, Files } from "lucide-react";

import { api } from "@/lib/api";
import type { DataFile, DatasetFile, Instance, Usecase } from "@/lib/types";
import { formatBytes, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState, PageHeader } from "@/components/ui/primitives";
import { Skeleton } from "@/components/ui/skeleton";

/** Everything this account has uploaded, across every use case and instance. */
export default function UserFilesPage() {
  const usecases = useQuery({
    queryKey: ["usecases"],
    queryFn: () => api.get<Usecase[]>("/usecases"),
  });

  const instanceQueries = useQueries({
    queries: (usecases.data ?? []).map((usecase) => ({
      queryKey: ["instances", usecase.id],
      queryFn: () => api.get<Instance[]>(`/instances?usecase=${usecase.id}`),
    })),
  });

  const usecaseFiles = useQueries({
    queries: (usecases.data ?? []).map((usecase) => ({
      queryKey: ["usecase-files", usecase.id],
      queryFn: () => api.get<DataFile[]>(`/usecases/${usecase.id}/files`),
    })),
  });

  const allInstances = instanceQueries.flatMap((q) => q.data ?? []);

  const instanceFiles = useQueries({
    queries: allInstances.map((instance) => ({
      queryKey: ["instance-files", instance.id],
      queryFn: () => api.get<DataFile[]>(`/instances/${instance.id}/files`),
    })),
  });

  const instanceDatasets = useQueries({
    queries: allInstances.map((instance) => ({
      queryKey: ["instance-datasets", instance.id],
      queryFn: () => api.get<DatasetFile[]>(`/instances/${instance.id}/datasets`),
    })),
  });

  if (usecases.isLoading) return <Skeleton className="h-48" />;

  const groups = (usecases.data ?? []).map((usecase, index) => ({
    usecase,
    documents: usecaseFiles[index]?.data ?? [],
    instances: (instanceQueries[index]?.data ?? []).map((instance) => {
      const at = allInstances.findIndex((i) => i.id === instance.id);
      return {
        instance,
        documents: instanceFiles[at]?.data ?? [],
        datasets: instanceDatasets[at]?.data ?? [],
      };
    }),
  }));

  const total = groups.reduce(
    (sum, g) =>
      sum +
      g.documents.length +
      g.instances.reduce((s, i) => s + i.documents.length + i.datasets.length, 0),
    0
  );

  if (!total) {
    return (
      <>
        <PageHeader title="User Files" description="Everything you have uploaded." />
        <EmptyState
          icon={Files}
          title="No files yet"
          description="Documents and datasets you upload to a use case or instance appear here."
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="User Files"
        description={`${total} ${total === 1 ? "file" : "files"} across your use cases.`}
      />

      <div className="flex flex-col gap-6">
        {groups.map(({ usecase, documents, instances }) => (
          <Card key={usecase.id}>
            <CardHeader>
              <CardTitle>
                <Link
                  href={`/dashboard/use-cases/${usecase.id}`}
                  className="hover:underline underline-offset-4"
                >
                  {usecase.name}
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {documents.length ? (
                <FileList
                  title="Use case documents"
                  files={documents}
                  downloadBase={`/usecases/${usecase.id}/files`}
                />
              ) : null}
              {instances.map(({ instance, documents: docs, datasets }) =>
                docs.length || datasets.length ? (
                  <div key={instance.id} className="flex flex-col gap-2">
                    <p className="text-sm font-medium">{instance.name}</p>
                    {datasets.length ? (
                      <FileList
                        title="Datasets"
                        files={datasets}
                        downloadBase={`/instances/${instance.id}/datasets`}
                      />
                    ) : null}
                    {docs.length ? (
                      <FileList
                        title="Documents"
                        files={docs}
                        downloadBase={`/instances/${instance.id}/files`}
                      />
                    ) : null}
                  </div>
                ) : null
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}

function FileList({
  title,
  files,
  downloadBase,
}: {
  title: string;
  files: (DataFile | DatasetFile)[];
  /** Path prefix this file's id and `/download` are appended to. */
  downloadBase: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-xs text-muted-foreground">{title}</p>
      <ul className="flex flex-col gap-1.5">
        {files.map((file) => (
          <li key={file.id} className="flex items-center gap-2 rounded-md bg-muted/60 px-3 py-2 text-sm">
            <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
            <span className="min-w-0 flex-1 truncate">{file.filename}</span>
            <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
              {formatBytes(file.size)}
            </span>
            <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
              {formatDate(file.created_at)}
            </span>
            <Button asChild size="icon" variant="ghost" className="size-7 shrink-0">
              <a
                href={api.url(`${downloadBase}/${file.id}/download`)}
                target="_blank"
                rel="noreferrer"
                download={file.filename}
                aria-label={`Download ${file.filename}`}
              >
                <Download className="size-4" />
              </a>
            </Button>
          </li>
        ))}
      </ul>
    </div>
  );
}
