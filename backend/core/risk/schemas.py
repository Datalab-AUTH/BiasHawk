from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ============= AI System Documentation =============
class GeneralInformation(BaseModel):
    ai_system_name: str
    version_release_date: str
    provider_organization_name: str
    responsible_person_team: str
    contact_information: str


class SystemOverview(BaseModel):
    intended_purposes: str
    domain_of_use: str
    user_groups: List[str]
    deployment_environment: str
    risk_category: str


class ModelAndAlgorithms(BaseModel):
    model_type: str
    training_algorithms: str
    explainability_techniques: List[str]
    validation_methodology: str


class HumanOversight(BaseModel):
    human_in_the_loop: bool
    oversight_procedures: List[str]
    user_training: List[str]


class Cybersecurity(BaseModel):
    security_measures: List[str]
    robustness: str


class LoggingAndDocumentation(BaseModel):
    logs_maintained: bool
    retention_period: str
    auditability: List[str]


class GDPRConformityAssessment(BaseModel):
    assessment_performed: bool
    notified_body: str
    outcome: str


class AISystemDocumentation(BaseModel):
    general_information: GeneralInformation
    system_overview: SystemOverview
    model_and_algorithms: ModelAndAlgorithms
    human_oversight: HumanOversight
    cybersecurity: Cybersecurity
    logging_and_documentation: LoggingAndDocumentation
    gdpr_conformity_assessment: GDPRConformityAssessment


# ============= Data Description =============
class DataOverview(BaseModel):
    Data_Use_Description: str
    Types_of_Data_Used: List[str]
    Sources_of_Data: str
    Purpose_of_Data_Use: str
    High_Risk_Data_Handling: bool


class DataCollectionAndOrigin(BaseModel):
    Data_Collected_From: List[str]
    Consent_Mechanism_Documented: bool
    Anonymization_or_Pseudonymization_Applied: bool
    Sensitive_Data_Included: bool


class DataQualityAssurance(BaseModel):
    Data_Cleaning_Steps: List[str]
    Missing_Data_Handling: str
    Duplication_Removal: str
    Preprocessing_Methods: List[str]
    Validation_Methods: str


class DataManagementAndGovernance(BaseModel):
    Data_Retention_Policy: str
    Access_Control_Mechanisms: List[str]
    Data_Lineage_and_Provenance_Tracking: bool
    Data_Minimization_Measures: List[str]
    Storage_Location_and_Jurisdiction: str
    Compliance_with_GDPR: bool


class MonitoringAndUpdates(BaseModel):
    Frequency_of_Data_Updates: str
    User_Feedback_Integrated_into_Data_Updates: bool


class AIDataComplianceForm(BaseModel):
    Data_Overview: DataOverview
    Data_Collection_and_Origin: DataCollectionAndOrigin
    Data_Quality_Assurance: DataQualityAssurance
    Data_Management_and_Governance: DataManagementAndGovernance
    Monitoring_and_Updates: MonitoringAndUpdates


# ============= Data Profile =============
class DataProfileMetrics(BaseModel):
    num_rows: int
    num_columns: int
    memory_usage: str
    duplicate_rows: int
    duplicate_percentage: float
    missing_data_status: str
    data_types_composition: Dict[str, int]


# ============= Risk Assessment Input =============
class RiskAssessmentInput(BaseModel):
    """Input without summary fields."""

    # Optional system context
    ai_system_documentation: Optional[AISystemDocumentation] = None
    data_compliance_form: Optional[AIDataComplianceForm] = None

    # Core metrics (required)
    data_profile_metrics: Optional[DataProfileMetrics] = None
    data_quality_metrics: Optional[Dict[str, Any]] = None
    bias_assessment_results: Optional[Dict[str, Any]] = None
    drift_metrics: Optional[List[Dict[str, Any]]] = None
    bias_drift_events: Optional[List[Dict[str, Any]]] = None

    timestamp: datetime = Field(default_factory=datetime.now)


# ============= Risk Assessment Output =============
class RiskLevel(BaseModel):
    level: str
    score: float
    justification: str


class PrioritizedAction(BaseModel):
    priority: int
    risk_category: str
    risk_description: str
    mitigation_strategy: str
    responsible_party: str
    timeline: str
    success_metrics: List[str]


class NISTRiskAssessmentReport(BaseModel):
    report_generated: datetime
    assessment_period: str
    report_version: str
    ai_system_name: str

    executive_summary: str
    overall_risk_level: RiskLevel
    critical_findings: List[str]

    govern_section: Dict[str, Any]
    map_section: Dict[str, Any]
    measure_section: Dict[str, Any]
    manage_section: Dict[str, Any]

    prioritized_actions: List[PrioritizedAction]

    immediate_actions: List[str]
    short_term_actions: List[str]
    long_term_actions: List[str]

    full_report_markdown: str
