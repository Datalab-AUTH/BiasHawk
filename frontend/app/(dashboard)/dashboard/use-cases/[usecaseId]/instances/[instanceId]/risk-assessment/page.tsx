"use client";

import { useParams } from "next/navigation";

import type { RiskReportData } from "@/lib/types";
import { AnalysisPage } from "@/components/dashboard/analysis-page";
import { ReportView } from "@/components/dashboard/report-view";
import { RiskSummary } from "@/components/dashboard/risk-summary";

export default function RiskAssessmentPage() {
  const { instanceId } = useParams<{ instanceId: string }>();

  return (
    <AnalysisPage
      kind="risk_assessment"
      title="Risk Assessment"
      description="Every finding mapped to the NIST AI RMF, prioritised, with an EU AI Act compliance view."
      runDescription="Rewritten automatically whenever data quality or the bias assessment changes. Run it again to rebuild it from the current results."
      requires={(i) => Boolean(i.data_quality_report || i.metrics_report)}
      requiresLabel="Run Data Quality or the Bias Analysis first."
    >
      {(instance) => (
        <div className="flex flex-col gap-6">
          <RiskSummary data={instance.nist_risk_report_data as RiskReportData} />
          <ReportView
            markdown={instance.nist_risk_report}
            pdfPath={`/instances/${instanceId}/reports/risk/pdf`}
            emptyTitle="No risk assessment yet"
            emptyDescription="Run Data Quality or the Bias Analysis; the NIST report follows automatically."
          />
        </div>
      )}
    </AnalysisPage>
  );
}
