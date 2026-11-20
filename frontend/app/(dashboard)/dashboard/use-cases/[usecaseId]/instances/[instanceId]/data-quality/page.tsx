"use client";

import { useParams } from "next/navigation";

import type { QualityMetrics } from "@/lib/types";
import { AnalysisPage } from "@/components/dashboard/analysis-page";
import { ReportView } from "@/components/dashboard/report-view";
import { DatasetStats, WarningsList } from "@/components/dashboard/quality-summary";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DataQualityPage() {
  const { instanceId } = useParams<{ instanceId: string }>();

  return (
    <AnalysisPage
      kind="data_quality"
      title="Data Quality"
      description="Missing values, outliers, duplicates and inconsistent types, with a severity for each."
      requiresDataset
      runDescription="Check the dataset and write the quality report."
    >
      {(instance) => (
        <div className="flex flex-col gap-6">
          {"dataset" in (instance.quality_metrics ?? {}) ? (
            <DatasetStats metrics={instance.quality_metrics as QualityMetrics} />
          ) : null}

          {instance.quality_warnings?.length ? (
            <Card>
              <CardHeader>
                <CardTitle>Findings</CardTitle>
              </CardHeader>
              <CardContent>
                <WarningsList warnings={instance.quality_warnings} />
              </CardContent>
            </Card>
          ) : null}

          <ReportView
            markdown={instance.data_quality_report}
            pdfPath={`/instances/${instanceId}/reports/data-quality/pdf`}
            emptyTitle="No data quality report yet"
            emptyDescription="Run the analysis to generate one."
          />
        </div>
      )}
    </AnalysisPage>
  );
}
