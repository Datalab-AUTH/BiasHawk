"use client";

import { useParams } from "next/navigation";

import { AnalysisPage } from "@/components/dashboard/analysis-page";
import { FairnessMetrics } from "@/components/dashboard/fairness-metrics";
import { ReportView } from "@/components/dashboard/report-view";

export default function BiasAnalysisReportPage() {
  const { instanceId } = useParams<{ instanceId: string }>();

  return (
    <AnalysisPage
      kind="bias_report"
      title="Bias Analysis Report"
      description="The fairness findings written up for stakeholders, with the metrics behind them."
      runDescription="Written automatically after every bias assessment. Run it again to rewrite it from the current metrics."
      requires={(i) => Boolean(i.metrics_report)}
      requiresLabel="Run the bias assessment on the Setup tab first."
    >
      {(instance) => (
        <div className="flex flex-col gap-6">
          <FairnessMetrics
            results={instance.analysis_results}
            instanceId={instanceId}
            version={instance.updated_at}
          />
          <ReportView
            markdown={instance.final_bias_report || instance.metrics_report}
            /* The assessment writes three documents. The page reads the
               executive one, but all three are the user's to take. */
            downloads={[
              instance.final_bias_report && {
                label: "Executive report",
                path: `/instances/${instanceId}/reports/bias-final/pdf`,
              },
              instance.metrics_report && {
                label: "Metrics report",
                path: `/instances/${instanceId}/reports/bias-metrics/pdf`,
              },
              instance.warnings_report && {
                label: "Warnings report",
                path: `/instances/${instanceId}/reports/bias-warnings/pdf`,
              },
            ].filter(Boolean as unknown as (v: unknown) => v is { label: string; path: string })}
            emptyTitle="No bias report yet"
            emptyDescription="Run the bias assessment on the Setup tab; the report is written straight after it."
          />
        </div>
      )}
    </AnalysisPage>
  );
}
