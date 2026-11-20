/** Shapes returned by the API. */

export type User = {
  id: string;
  email: string;
  name: string;
  date_joined: string;
};

export type Usecase = {
  id: string;
  name: string;
  description: string;
  metadata: AISystemDocumentation | Record<string, never>;
  instance_count: number;
  created_at: string;
  updated_at: string;
};

export type Instance = {
  id: string;
  usecase: string;
  name: string;
  description: string;
  metadata: AIDataComplianceForm | Record<string, never>;
  dataset_sensitive_features: Record<string, SensitiveFeature>;
  /** Is there a source CSV to analyse? Nothing can run without one. */
  has_dataset: boolean;
  created_at: string;
  updated_at: string;
};

export type InstanceDetail = Instance & {
  data_profile_description: string;
  data_quality_description: string;
  data_quality_report: string;
  quality_metrics: QualityMetrics | Record<string, never>;
  quality_warnings: QualityWarning[];
  analysis_results: Record<string, unknown>;
  metrics_report: string;
  warnings_report: string;
  final_bias_report: string;
  nist_risk_report: string;
  nist_risk_report_data: RiskReportData | Record<string, never>;
};

export type SensitiveFeature = {
  score: number;
  by_keyword: boolean;
  by_llm: boolean;
  categories: string[];
  summary: string;
};

export type QualityMetrics = {
  features: Record<string, Record<string, number | string | null>>;
  dataset: { total_rows: number; total_columns: number; duplicate_rows: number };
};

export type Severity = "low" | "medium" | "high";

export type QualityWarning = {
  test_name: string;
  feature: string;
  description: string;
  severity: Severity;
  data: Record<string, unknown>;
};

export type RiskReportData = {
  overall_risk_level?: { level: string; score: number; justification: string };
  critical_findings?: string[];
  prioritized_actions?: Record<string, unknown>[];
};

export type JobKind =
  | "rag_ingest"
  | "usecase_extract"
  | "instance_extract"
  | "data_governance"
  | "data_quality"
  | "sensitive_features"
  | "bias_assessment"
  | "bias_report"
  | "drift"
  | "risk_assessment";

export type JobStatus = "queued" | "running" | "done" | "failed";

export type Job = {
  id: string;
  kind: JobKind;
  status: JobStatus;
  usecase: string | null;
  instance: string | null;
  attempts: number;
  error: string;
  result: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type DataFile = {
  id: string;
  filename: string;
  mime_type: string;
  size: number | null;
  created_at: string;
};

export type DatasetFile = DataFile & {
  kind: "source" | "export";
  csv_features: Record<string, string>;
  /**
   * Shape of the CSV as uploaded. Absent on datasets stored before the API
   * measured them, so treat a missing profile as "unknown", not as zero.
   */
  csv_profile?: { rows: number; distinct: Record<string, number> };
};

/**
 * Extracted use case documentation.
 *
 * Note the array fields , user_groups, oversight_procedures, user_training,
 * auditability, explainability_techniques and security_measures are all
 * `string[]`, matching the backend schema in core/agents/schemas.py.
 */
export type AISystemDocumentation = {
  general_information: {
    ai_system_name: string;
    version_release_date: string;
    provider_organization_name: string;
    responsible_person_team: string;
    contact_information: string;
  };
  system_overview: {
    intended_purposes: string;
    domain_of_use: string;
    user_groups: string[];
    deployment_environment: string;
    risk_category: string;
  };
  model_and_algorithms: {
    model_type: string;
    training_algorithms: string;
    explainability_techniques: string[];
    validation_methodology: string;
  };
  human_oversight: {
    human_in_the_loop: boolean;
    oversight_procedures: string[];
    user_training: string[];
  };
  cybersecurity: { security_measures: string[]; robustness: string };
  logging_and_documentation: {
    logs_maintained: boolean;
    retention_period: string;
    auditability: string[];
  };
  gdpr_conformity_assessment: {
    assessment_performed: boolean;
    notified_body: string;
    outcome: string;
  };
};

export type AIDataComplianceForm = {
  Data_Overview: {
    Data_Use_Description: string;
    Types_of_Data_Used: string[];
    Sources_of_Data: string;
    Purpose_of_Data_Use: string;
    High_Risk_Data_Handling: boolean;
  };
  Data_Collection_and_Origin: {
    Data_Collected_From: string[];
    Consent_Mechanism_Documented: boolean;
    Anonymization_or_Pseudonymization_Applied: boolean;
    Sensitive_Data_Included: boolean;
  };
  Data_Quality_Assurance: {
    Data_Cleaning_Steps: string[];
    Missing_Data_Handling: string;
    Duplication_Removal: string;
    Preprocessing_Methods: string[];
    Validation_Methods: string;
  };
  Data_Management_and_Governance: {
    Data_Retention_Policy: string;
    Access_Control_Mechanisms: string[];
    Data_Lineage_and_Provenance_Tracking: boolean;
    Data_Minimization_Measures: string[];
    Storage_Location_and_Jurisdiction: string;
    Compliance_with_GDPR: boolean;
  };
  Monitoring_and_Updates: {
    Frequency_of_Data_Updates: string;
    User_Feedback_Integrated_into_Data_Updates: boolean;
  };
};


export type DriftEvent = {
  event_type?: string;
  metric?: string;
  feature?: string;
  description?: string;
  baseline_value?: number;
  current_value?: number;
  severity?: string;
};

export type DriftWarning = {
  test_name?: string;
  feature?: string;
  description?: string;
  severity?: string;
  data?: Record<string, unknown>;
};

export type DriftRecord = {
  id: string;
  initial_instance: string;
  initial_instance_name: string;
  comparison_instance: string;
  comparison_instance_name: string;
  drift_detected: boolean;
  data_drift_summary: string;
  /** Stored as a JSON string by the handler. */
  data_drift_warnings: string;
  data_drift_metrics: DriftWarning[];
  bias_drift_detected: boolean;
  bias_drift_events: DriftEvent[];
  bias_drift_summary: string;
  final_drift_report: string;
  created_at: string;
  updated_at: string;
};
