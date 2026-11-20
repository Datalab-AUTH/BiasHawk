"use client";

import { useParams } from "next/navigation";
import { ChevronDown } from "lucide-react";

import { AnalysisPage } from "@/components/dashboard/analysis-page";
import { ReportView } from "@/components/dashboard/report-view";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

export default function DataGovernancePage() {
  const { instanceId } = useParams<{ instanceId: string }>();

  return (
    <AnalysisPage
      kind="data_governance"
      title="Data Governance"
      description="A structured profile of the dataset: shape, types, missingness and distributions."
      requiresDataset
      runDescription="Profile the dataset and summarise it for the record."
    >
      {(instance) => (
        <div className="flex flex-col gap-6">
          <ReportView
            markdown={instance.data_quality_description}
            pdfPath={`/instances/${instanceId}/reports/data-governance/pdf`}
            emptyTitle="No data governance report yet"
            emptyDescription="Run the analysis to generate one."
          />

          {/* The measurements the report above was written from. Folded away
              by default: it is long, and it is the evidence rather than the
              reading of it. */}
          {instance.data_profile_description?.trim() ? (
            <Collapsible className="rounded-lg border">
              <CollapsibleTrigger className="group flex w-full items-center justify-between gap-3 px-4 py-3 text-left">
                <span className="flex flex-col">
                  <span className="text-sm font-medium">Data profile description report</span>
                  <span className="text-xs text-muted-foreground">
                    The raw measurements the structured report was written from.
                  </span>
                </span>
                <ChevronDown
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-180"
                  aria-hidden
                />
              </CollapsibleTrigger>
              <CollapsibleContent className="border-t px-4 py-4">
                <ReportView
                  markdown={instance.data_profile_description}
                  pdfPath={`/instances/${instanceId}/reports/data-profile/pdf`}
                  emptyTitle="No data profile yet"
                />
              </CollapsibleContent>
            </Collapsible>
          ) : null}
        </div>
      )}
    </AnalysisPage>
  );
}
