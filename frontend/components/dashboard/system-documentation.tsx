"use client";

import type * as React from "react";
import { Check, Minus, X } from "lucide-react";

import type { AIDataComplianceForm, AISystemDocumentation } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const UNKNOWN = "unknown";

function isUnknown(value: unknown): boolean {
  if (typeof value === "string") return !value.trim() || value.trim().toLowerCase() === UNKNOWN;
  if (Array.isArray(value)) return value.length === 0 || value.every(isUnknown);
  return false;
}

/** Extraction fills gaps with "unknown"; render that as absence, not as a value. */
function Value({ value }: { value: string | string[] | boolean }) {
  if (typeof value === "boolean") {
    return value ? (
      <span className="inline-flex items-center gap-1.5 text-[var(--success)]">
        <Check className="size-4" aria-hidden />
        Yes
      </span>
    ) : (
      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
        <X className="size-4" aria-hidden />
        No
      </span>
    );
  }

  if (isUnknown(value)) {
    return (
      <span className="inline-flex items-center gap-1.5 text-muted-foreground">
        <Minus className="size-4" aria-hidden />
        Not stated in the documents
      </span>
    );
  }

  if (Array.isArray(value)) {
    return (
      <ul className="flex flex-col gap-1">
        {value.map((item, index) => (
          <li key={index} className="flex gap-2">
            <span className="text-muted-foreground">·</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    );
  }

  return <span>{value}</span>;
}

function Section({
  title,
  fields,
}: {
  title: string;
  fields: [string, string | string[] | boolean][];
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-border py-4 last:border-b-0">
      <h3 className="text-sm font-semibold">{title}</h3>
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[minmax(11rem,auto)_1fr]">
        {fields.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="text-sm">
              <Value value={value} />
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** The card with its controls, before there is anything to show in it. */
function RecordShell({ title, actions }: { title: string; actions?: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <CardTitle>{title}</CardTitle>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Nothing recorded yet. Open the details to upload documentation , it is read
          automatically , or fill the fields in yourself.
        </p>
      </CardContent>
    </Card>
  );
}

export function SystemDocumentation({
  data,
  actions,
}: {
  /** Null before anything has been extracted or entered. */
  data: AISystemDocumentation | null;
  actions?: React.ReactNode;
}) {
  if (!data) return <RecordShell title="AI System Information" actions={actions} />;

  const g = data.general_information;
  const s = data.system_overview;
  const m = data.model_and_algorithms;
  const h = data.human_oversight;
  const c = data.cybersecurity;
  const l = data.logging_and_documentation;
  const gdpr = data.gdpr_conformity_assessment;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <CardTitle>AI System Information</CardTitle>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </CardHeader>
      <CardContent className="flex flex-col">
        <Section
          title="General information"
          fields={[
            ["System name", g.ai_system_name],
            ["Version / release", g.version_release_date],
            ["Provider", g.provider_organization_name],
            ["Responsible team", g.responsible_person_team],
            ["Compliance contact", g.contact_information],
          ]}
        />
        <Section
          title="System overview"
          fields={[
            ["Intended purpose", s.intended_purposes],
            ["Domain of use", s.domain_of_use],
            ["User groups", s.user_groups],
            ["Deployment", s.deployment_environment],
            ["Risk category", s.risk_category],
          ]}
        />
        <Section
          title="Model and algorithms"
          fields={[
            ["Model type", m.model_type],
            ["Training algorithms", m.training_algorithms],
            ["Explainability", m.explainability_techniques],
            ["Validation", m.validation_methodology],
          ]}
        />
        <Section
          title="Human oversight"
          fields={[
            ["Human in the loop", h.human_in_the_loop],
            ["Oversight procedures", h.oversight_procedures],
            ["User training", h.user_training],
          ]}
        />
        <Section
          title="Cybersecurity"
          fields={[
            ["Security measures", c.security_measures],
            ["Robustness", c.robustness],
          ]}
        />
        <Section
          title="Logging and documentation"
          fields={[
            ["Logs maintained", l.logs_maintained],
            ["Retention period", l.retention_period],
            ["Auditability", l.auditability],
          ]}
        />
        <Section
          title="GDPR conformity"
          fields={[
            ["Assessment performed", gdpr.assessment_performed],
            ["Notified body", gdpr.notified_body],
            ["Outcome", gdpr.outcome],
          ]}
        />
      </CardContent>
    </Card>
  );
}

export function DataComplianceForm({
  data,
  actions,
}: {
  data: AIDataComplianceForm | null;
  actions?: React.ReactNode;
}) {
  if (!data) return <RecordShell title="Data compliance form" actions={actions} />;

  const o = data.Data_Overview;
  const col = data.Data_Collection_and_Origin;
  const q = data.Data_Quality_Assurance;
  const gov = data.Data_Management_and_Governance;
  const mon = data.Monitoring_and_Updates;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-3">
        <CardTitle>Data compliance form</CardTitle>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </CardHeader>
      <CardContent className="flex flex-col">
        <Section
          title="Data overview"
          fields={[
            ["Use description", o.Data_Use_Description],
            ["Types of data", o.Types_of_Data_Used],
            ["Sources", o.Sources_of_Data],
            ["Purpose", o.Purpose_of_Data_Use],
            ["High-risk handling", o.High_Risk_Data_Handling],
          ]}
        />
        <Section
          title="Collection and origin"
          fields={[
            ["Collected from", col.Data_Collected_From],
            ["Consent documented", col.Consent_Mechanism_Documented],
            ["Anonymised or pseudonymised", col.Anonymization_or_Pseudonymization_Applied],
            ["Sensitive data included", col.Sensitive_Data_Included],
          ]}
        />
        <Section
          title="Quality assurance"
          fields={[
            ["Cleaning steps", q.Data_Cleaning_Steps],
            ["Missing data", q.Missing_Data_Handling],
            ["Duplicate removal", q.Duplication_Removal],
            ["Preprocessing", q.Preprocessing_Methods],
            ["Validation", q.Validation_Methods],
          ]}
        />
        <Section
          title="Management and governance"
          fields={[
            ["Retention policy", gov.Data_Retention_Policy],
            ["Access controls", gov.Access_Control_Mechanisms],
            ["Lineage tracked", gov.Data_Lineage_and_Provenance_Tracking],
            ["Minimisation", gov.Data_Minimization_Measures],
            ["Storage and jurisdiction", gov.Storage_Location_and_Jurisdiction],
            ["GDPR compliant", gov.Compliance_with_GDPR],
          ]}
        />
        <Section
          title="Monitoring and updates"
          fields={[
            ["Update frequency", mon.Frequency_of_Data_Updates],
            ["User feedback integrated", mon.User_Feedback_Integrated_into_Data_Updates],
          ]}
        />
      </CardContent>
    </Card>
  );
}
