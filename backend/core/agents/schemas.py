"""
Extraction schemas, carried over from the old agents verbatim in shape.

Field names, nesting and types match `usecase-agent/models.py` and
`instance-agent/models.py` exactly, so the JSON stored on Usecase.metadata and
Instance.metadata is the same shape the dashboard already renders.

The one change: every field has a default. The old schemas marked everything
required, so a model that omitted a single field failed validation and the whole
extraction was lost. Defaults encode the instruction the old prompt gave in
prose , "when there is no answer, fill the json with 'unknown'" , as a property
of the schema instead, which means a partial answer degrades to `unknown`
per-field rather than failing outright.
"""

from pydantic import BaseModel, Field

UNKNOWN = "unknown"


def _unknown_list():
    return [UNKNOWN]


# ---------------------------------------------------------------------------
# use case: AI system documentation
# ---------------------------------------------------------------------------


class GeneralInformation(BaseModel):
    ai_system_name: str = UNKNOWN
    version_release_date: str = UNKNOWN
    provider_organization_name: str = UNKNOWN
    responsible_person_team: str = UNKNOWN
    contact_information: str = UNKNOWN


class SystemOverview(BaseModel):
    intended_purposes: str = UNKNOWN
    domain_of_use: str = UNKNOWN
    user_groups: list[str] = Field(default_factory=_unknown_list)
    deployment_environment: str = UNKNOWN
    risk_category: str = UNKNOWN


class ModelAndAlgorithms(BaseModel):
    model_type: str = UNKNOWN
    training_algorithms: str = UNKNOWN
    explainability_techniques: list[str] = Field(default_factory=_unknown_list)
    validation_methodology: str = UNKNOWN


class HumanOversight(BaseModel):
    human_in_the_loop: bool = False
    oversight_procedures: list[str] = Field(default_factory=_unknown_list)
    user_training: list[str] = Field(default_factory=_unknown_list)


class Cybersecurity(BaseModel):
    security_measures: list[str] = Field(default_factory=_unknown_list)
    robustness: str = UNKNOWN


class LoggingAndDocumentation(BaseModel):
    logs_maintained: bool = False
    retention_period: str = UNKNOWN
    auditability: list[str] = Field(default_factory=_unknown_list)


class GDPRConformityAssessment(BaseModel):
    assessment_performed: bool = False
    notified_body: str = UNKNOWN
    outcome: str = UNKNOWN


class AISystemDocumentation(BaseModel):
    general_information: GeneralInformation = Field(default_factory=GeneralInformation)
    system_overview: SystemOverview = Field(default_factory=SystemOverview)
    model_and_algorithms: ModelAndAlgorithms = Field(default_factory=ModelAndAlgorithms)
    human_oversight: HumanOversight = Field(default_factory=HumanOversight)
    cybersecurity: Cybersecurity = Field(default_factory=Cybersecurity)
    logging_and_documentation: LoggingAndDocumentation = Field(
        default_factory=LoggingAndDocumentation
    )
    gdpr_conformity_assessment: GDPRConformityAssessment = Field(
        default_factory=GDPRConformityAssessment
    )


# ---------------------------------------------------------------------------
# instance: AI data compliance form
# ---------------------------------------------------------------------------


class DataOverview(BaseModel):
    Data_Use_Description: str = UNKNOWN
    Types_of_Data_Used: list[str] = Field(default_factory=_unknown_list)
    Sources_of_Data: str = UNKNOWN
    Purpose_of_Data_Use: str = UNKNOWN
    High_Risk_Data_Handling: bool = False


class DataCollectionAndOrigin(BaseModel):
    Data_Collected_From: list[str] = Field(default_factory=_unknown_list)
    Consent_Mechanism_Documented: bool = False
    Anonymization_or_Pseudonymization_Applied: bool = False
    Sensitive_Data_Included: bool = False


class DataQualityAssurance(BaseModel):
    Data_Cleaning_Steps: list[str] = Field(default_factory=_unknown_list)
    Missing_Data_Handling: str = UNKNOWN
    Duplication_Removal: str = UNKNOWN
    Preprocessing_Methods: list[str] = Field(default_factory=_unknown_list)
    Validation_Methods: str = UNKNOWN


class DataManagementAndGovernance(BaseModel):
    Data_Retention_Policy: str = UNKNOWN
    Access_Control_Mechanisms: list[str] = Field(default_factory=_unknown_list)
    Data_Lineage_and_Provenance_Tracking: bool = False
    Data_Minimization_Measures: list[str] = Field(default_factory=_unknown_list)
    Storage_Location_and_Jurisdiction: str = UNKNOWN
    Compliance_with_GDPR: bool = False


class MonitoringAndUpdates(BaseModel):
    Frequency_of_Data_Updates: str = UNKNOWN
    User_Feedback_Integrated_into_Data_Updates: bool = False


class AIDataComplianceForm(BaseModel):
    Data_Overview: DataOverview = Field(default_factory=DataOverview)
    Data_Collection_and_Origin: DataCollectionAndOrigin = Field(
        default_factory=DataCollectionAndOrigin
    )
    Data_Quality_Assurance: DataQualityAssurance = Field(default_factory=DataQualityAssurance)
    Data_Management_and_Governance: DataManagementAndGovernance = Field(
        default_factory=DataManagementAndGovernance
    )
    Monitoring_and_Updates: MonitoringAndUpdates = Field(default_factory=MonitoringAndUpdates)


# ---------------------------------------------------------------------------
# the questions each agent puts to the documents, unchanged from the old agents
# ---------------------------------------------------------------------------

USECASE_QUESTIONS = [
    "What is the name of the AI system?",
    "What is the version number and release date?",
    "What is the name of the provider organization?",
    "Who is the responsible person or team?",
    "What is the contact information for compliance inquiries?",
    "What is the intended purpose of the AI system?",
    "In which domain is the AI system used?",
    "Who are the primary user groups?",
    "Where is the system deployed (e.g. cloud, on-premise, region)?",
    "What is the risk category of the system (e.g. employment, healthcare)?",
    "What type of model is used?",
    "What training algorithms were applied?",
    "What explainability techniques are implemented?",
    "What validation methodology was used?",
    "Is there a human-in-the-loop mechanism?",
    "What oversight procedures are in place?",
    "What kind of user training is provided?",
    "What security measures are implemented?",
    "How is robustness ensured (e.g. adversarial testing, retraining)?",
    "Are logs maintained?",
    "What is the retention period for logs?",
    "What auditability measures are in place?",
    "Has a GDPR conformity assessment been performed?",
    "Which notified body conducted the assessment?",
    "What was the outcome of the assessment?",
]

INSTANCE_QUESTIONS = [
    "What types of data are used (text, numerical, categorical, images)?",
    "What are the data sources?",
    "What is the purpose of data use (training, validation, inference)?",
    "Is data handling high-risk?",
    "Where was the data collected from?",
    "Is consent documented?",
    "Is data anonymized or pseudonymized?",
    "Is sensitive data included?",
    "What data cleaning steps are taken?",
    "How is missing data handled?",
    "How are duplicates removed?",
    "What preprocessing methods are used?",
    "How is data quality validated?",
    "What is the data retention policy?",
    "What are the data access controls?",
    "Is data lineage tracked?",
    "What data minimization measures are in place?",
    "Where is data stored and under what jurisdiction?",
    "Is the system GDPR compliant?",
    "How often is data updated?",
    "Is user feedback used for updates?",
]
