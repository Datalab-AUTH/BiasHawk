"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Minimize2 } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useAutofillLocks, useSelection } from "@/lib/store";
import type { AISystemDocumentation, Usecase } from "@/lib/types";
import {
  AutofillStep,
  MinimisedRun,
  useAutofillRun,
} from "@/components/dashboard/autofill-step";
import {
  BooleanField,
  ListField,
  StepGrid,
  Stepper,
  TextField,
} from "@/components/dashboard/stepper";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm-dialog";

const UNKNOWN = "unknown";

function emptyRecord(): AISystemDocumentation {
  return {
    general_information: {
      ai_system_name: "",
      version_release_date: "",
      provider_organization_name: "",
      responsible_person_team: "",
      contact_information: "",
    },
    system_overview: {
      intended_purposes: "",
      domain_of_use: "",
      user_groups: [],
      deployment_environment: "",
      risk_category: "",
    },
    model_and_algorithms: {
      model_type: "",
      training_algorithms: "",
      explainability_techniques: [],
      validation_methodology: "",
    },
    human_oversight: { human_in_the_loop: false, oversight_procedures: [], user_training: [] },
    cybersecurity: { security_measures: [], robustness: "" },
    logging_and_documentation: { logs_maintained: false, retention_period: "", auditability: [] },
    gdpr_conformity_assessment: { assessment_performed: false, notified_body: "", outcome: "" },
  };
}

/** Extraction writes "unknown" into gaps; show those as blank so they read as unfilled. */
function blankUnknowns(record: AISystemDocumentation): AISystemDocumentation {
  const clean = (v: string) => (v?.trim().toLowerCase() === UNKNOWN ? "" : (v ?? ""));
  const cleanList = (v: string[]) =>
    (v ?? []).filter((item) => item?.trim().toLowerCase() !== UNKNOWN);

  return {
    general_information: Object.fromEntries(
      Object.entries(record.general_information).map(([k, v]) => [k, clean(v as string)])
    ) as AISystemDocumentation["general_information"],
    system_overview: {
      ...record.system_overview,
      intended_purposes: clean(record.system_overview.intended_purposes),
      domain_of_use: clean(record.system_overview.domain_of_use),
      deployment_environment: clean(record.system_overview.deployment_environment),
      risk_category: clean(record.system_overview.risk_category),
      user_groups: cleanList(record.system_overview.user_groups),
    },
    model_and_algorithms: {
      ...record.model_and_algorithms,
      model_type: clean(record.model_and_algorithms.model_type),
      training_algorithms: clean(record.model_and_algorithms.training_algorithms),
      validation_methodology: clean(record.model_and_algorithms.validation_methodology),
      explainability_techniques: cleanList(record.model_and_algorithms.explainability_techniques),
    },
    human_oversight: {
      ...record.human_oversight,
      oversight_procedures: cleanList(record.human_oversight.oversight_procedures),
      user_training: cleanList(record.human_oversight.user_training),
    },
    cybersecurity: {
      robustness: clean(record.cybersecurity.robustness),
      security_measures: cleanList(record.cybersecurity.security_measures),
    },
    logging_and_documentation: {
      ...record.logging_and_documentation,
      retention_period: clean(record.logging_and_documentation.retention_period),
      auditability: cleanList(record.logging_and_documentation.auditability),
    },
    gdpr_conformity_assessment: {
      ...record.gdpr_conformity_assessment,
      notified_body: clean(record.gdpr_conformity_assessment.notified_body),
      outcome: clean(record.gdpr_conformity_assessment.outcome),
    },
  };
}

/**
 * Everything the Save button would write, as one comparable string.
 *
 * Closing only asks for confirmation when this differs from what the dialog
 * opened with , leaving without having changed anything loses nothing, so it
 * has nothing to ask about.
 */
function snapshot(name: string, description: string, record: AISystemDocumentation) {
  return JSON.stringify({ name: name.trim(), description: description.trim(), record });
}

export function CreateUsecaseDialog({
  open,
  onOpenChange,
  /** Pass an existing use case to edit it instead of creating a new one. */
  editing,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing?: Usecase | null;
}) {
  const isEditing = Boolean(editing);
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const setUseCase = useSelection((s) => s.setUseCase);

  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [record, setRecord] = useState<AISystemDocumentation>(emptyRecord);
  const [usecaseId, setUsecaseId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Put out of the way while a document is being read, rather than closed ,
  // closing throws the half-built record away, and the read is still going.
  const [minimised, setMinimised] = useState(false);
  // What the form held when it opened, to tell an edit from an idle look.
  const baseline = useRef(snapshot("", "", emptyRecord()));

  // Owned here, not by the step: minimising unmounts the step, and the read
  // has to survive that , it is the whole point of minimising.
  const autofill = useAutofillRun({
    scope: "usecases",
    ensureScopeId: ensureRecord,
    extractKind: "usecase_extract",
    onExtracted: loadExtracted,
  });
  const autofilling = autofill.busy;

  // Out of sight, the extraction is still writing to this record. Close it for
  // editing everywhere else until it lands, or the two overwrite each other.
  const lock = useAutofillLocks((s) => s.lock);
  const unlock = useAutofillLocks((s) => s.unlock);
  useEffect(() => {
    if (!autofilling || !usecaseId) return;
    lock(usecaseId);
    return () => unlock(usecaseId);
  }, [autofilling, usecaseId, lock, unlock]);

  /**
   * Create the record only when something needs it to exist , uploading a
   * document. The manual path creates it once, at Finish. Nothing is written
   * to the database for a dialog the user opens and closes again.
   */
  async function ensureRecord(): Promise<string> {
    if (usecaseId) return usecaseId;
    const created = await api.post<Usecase>("/usecases", { name: "Untitled use case", description: "" });
    setUsecaseId(created.id);
    return created.id;
  }

  // Load whatever is being edited each time the dialog opens, so reopening
  // after a change shows the current values rather than the ones from before.
  useEffect(() => {
    if (!open) return;
    if (editing) {
      const loaded =
        "general_information" in (editing.metadata ?? {})
          ? blankUnknowns(editing.metadata as never)
          : emptyRecord();
      const loadedName = editing.name === "Untitled use case" ? "" : editing.name;
      const loadedDescription = editing.description ?? "";
      setRecord(loaded);
      setName(loadedName);
      setDescription(loadedDescription);
      setUsecaseId(editing.id);
      baseline.current = snapshot(loadedName, loadedDescription, loaded);
    }
  }, [open, editing]);

  function reset() {
    setStep(0);
    setName("");
    setDescription("");
    setRecord(emptyRecord());
    setMinimised(false);
    baseline.current = snapshot("", "", emptyRecord());
    // The run's "details filled in" note describes values that just went away.
    autofill.reset();
  }

  async function discard() {
    // Closing an edit dialog must not delete the thing being edited , only a
    // half-finished creation is thrown away.
    if (isEditing) {
      setUsecaseId(null);
      reset();
      return;
    }
    if (usecaseId) await api.delete(`/usecases/${usecaseId}`).catch(() => null);
    setUsecaseId(null);
    reset();
    void queryClient.invalidateQueries({ queryKey: ["usecases"] });
  }

  /** Is there anything closing would throw away? */
  function dirty() {
    // A record created for an upload is deleted on close, typed into or not.
    if (!isEditing && usecaseId) return true;
    return snapshot(name, description, record) !== baseline.current;
  }

  async function requestClose() {
    if (dirty()) {
      const ok = await confirm({
        title: isEditing ? "Close without saving?" : "Discard this use case?",
        description: isEditing
          ? "Anything you changed since opening this is lost. The use case itself stays as it was."
          : "The use case you started is deleted, along with any document uploaded to it.",
        confirmLabel: isEditing ? "Close" : "Discard",
        destructive: true,
      });
      if (!ok) return;
    }
    await discard();
    onOpenChange(false);
  }

  async function requestReset() {
    const ok = await confirm({
      title: "Reset all fields?",
      description: "Every step goes back to empty, including anything filled in from a document.",
      confirmLabel: "Reset",
      destructive: true,
    });
    if (ok) reset();
  }

  async function loadExtracted(id?: string) {
    // `id` comes from the autofill step: it created the record, so it knows
    // the id before this component's state does.
    const target = id ?? usecaseId;
    if (!target) return;
    const usecase = await api.get<Usecase>(`/usecases/${target}`);
    const metadata = usecase.metadata as AISystemDocumentation;
    if (metadata && "general_information" in metadata) {
      const cleaned = blankUnknowns(metadata);
      // The extracted system name is a far better default than "Untitled".
      const filledName = name || cleaned.general_information.ai_system_name || "";
      const filledDescription = description || cleaned.system_overview.intended_purposes || "";
      setRecord(cleaned);
      if (!name) setName(filledName);
      if (!description) setDescription(filledDescription);
      // These came from the record itself, so they are not unsaved edits.
      baseline.current = snapshot(filledName, filledDescription, cleaned);
    }
  }

  // Minimised, the dialog cannot report the outcome itself , the user may be
  // on another page by now. Say it once, where they are.
  const announced = useRef<string>("");
  useEffect(() => {
    if (!minimised) {
      announced.current = "";
      return;
    }
    if (autofill.phase !== "done" && autofill.phase !== "error") return;
    if (announced.current === autofill.phase) return;
    announced.current = autofill.phase;
    if (autofill.phase === "done") {
      toast.success("Your document has been read. Reopen the use case to review the details.");
    } else {
      toast.error(autofill.error ?? "Could not read that document.");
    }
  }, [minimised, autofill.phase, autofill.error]);

  async function finish() {
    const ok = await confirm({
      title: isEditing ? "Save these changes?" : "Create this use case?",
      description: isEditing
        ? "The details you entered replace what is on the use case now."
        : "The use case is created with the details you entered. You can edit them afterwards.",
      confirmLabel: isEditing ? "Save changes" : "Create use case",
    });
    if (!ok) return;

    setSaving(true);
    try {
      const body = {
        name: name.trim() || record.general_information.ai_system_name || "Untitled use case",
        description: description.trim(),
        metadata: record,
      };
      // The manual path never created a record, so Finish is the create.
      const saved = usecaseId
        ? await api.patch<Usecase>(`/usecases/${usecaseId}`, body)
        : await api.post<Usecase>("/usecases", body);
      toast.success(isEditing ? "Use case updated." : "Use case created.");
      setUseCase(saved.id, saved.name);
      void queryClient.invalidateQueries({ queryKey: ["usecases"] });
      setUsecaseId(null);
      reset();
      onOpenChange(false);
    } catch {
      toast.error("Could not save the use case.");
    } finally {
      setSaving(false);
    }
  }

  const g = record.general_information;
  const s = record.system_overview;
  const m = record.model_and_algorithms;
  const h = record.human_oversight;
  const c = record.cybersecurity;
  const l = record.logging_and_documentation;
  const gdpr = record.gdpr_conformity_assessment;

  const patch = <K extends keyof AISystemDocumentation>(
    section: K,
    changes: Partial<AISystemDocumentation[K]>
  ) => setRecord((prev) => ({ ...prev, [section]: { ...prev[section], ...changes } }));

  const steps = [
    { title: "Autofill", description: "Fill in the details by uploading your files." },
    { title: "General", description: "Who provides the system, and how to reach them." },
    { title: "Overview", description: "What the system is for and where it runs." },
    { title: "Model", description: "How the model is built and validated." },
    { title: "Oversight", description: "How people supervise the system." },
    { title: "Security", description: "How the system is protected." },
    { title: "Logging", description: "What is recorded, and for how long." },
    { title: "GDPR", description: "Conformity assessment status." },
  ];

  const content = [
    <AutofillStep key="autofill" run={autofill} scope="usecases" scopeId={usecaseId} />,

    <StepGrid key="general">
      <TextField
        label="Use case name"
        value={name}
        onChange={setName}
        hint="How it appears in your list."
      />
      <TextField
        label="AI system name"
        value={g.ai_system_name}
        onChange={(v) => patch("general_information", { ai_system_name: v })}
      />
      <TextField
        label="Version / release date"
        value={g.version_release_date}
        onChange={(v) => patch("general_information", { version_release_date: v })}
      />
      <TextField
        label="Provider organisation"
        value={g.provider_organization_name}
        onChange={(v) => patch("general_information", { provider_organization_name: v })}
      />
      <TextField
        label="Responsible person or team"
        value={g.responsible_person_team}
        onChange={(v) => patch("general_information", { responsible_person_team: v })}
      />
      <TextField
        label="Compliance contact"
        value={g.contact_information}
        onChange={(v) => patch("general_information", { contact_information: v })}
        hint="An email address or a team inbox."
      />
      <TextField
        label="Short description"
        multiline
        span="full"
        value={description}
        onChange={setDescription}
        hint="A sentence or two on what this use case covers."
      />
    </StepGrid>,

    <StepGrid key="overview">
      <TextField
        label="Domain of use"
        value={s.domain_of_use}
        onChange={(v) => patch("system_overview", { domain_of_use: v })}
      />
      <TextField
        label="Deployment environment"
        value={s.deployment_environment}
        onChange={(v) => patch("system_overview", { deployment_environment: v })}
      />
      <TextField
        label="Risk category"
        value={s.risk_category}
        onChange={(v) => patch("system_overview", { risk_category: v })}
        hint="For example: high-risk under the EU AI Act."
      />
      <TextField
        label="Intended purpose"
        multiline
        span={2}
        value={s.intended_purposes}
        onChange={(v) => patch("system_overview", { intended_purposes: v })}
      />
      <ListField
        label="User groups"
        value={s.user_groups}
        onChange={(v) => patch("system_overview", { user_groups: v })}
      />
    </StepGrid>,

    <StepGrid key="model">
      <TextField
        label="Model type"
        value={m.model_type}
        onChange={(v) => patch("model_and_algorithms", { model_type: v })}
      />
      <TextField
        label="Training algorithms"
        value={m.training_algorithms}
        onChange={(v) => patch("model_and_algorithms", { training_algorithms: v })}
      />
      <TextField
        label="Validation methodology"
        multiline
        span={2}
        value={m.validation_methodology}
        onChange={(v) => patch("model_and_algorithms", { validation_methodology: v })}
      />
      <ListField
        label="Explainability techniques"
        value={m.explainability_techniques}
        onChange={(v) => patch("model_and_algorithms", { explainability_techniques: v })}
      />
    </StepGrid>,

    <StepGrid key="oversight">
      <BooleanField
        label="Is there a human in the loop?"
        span="full"
        value={h.human_in_the_loop}
        onChange={(v) => patch("human_oversight", { human_in_the_loop: v })}
      />
      <ListField
        label="Oversight procedures"
        value={h.oversight_procedures}
        onChange={(v) => patch("human_oversight", { oversight_procedures: v })}
      />
      <ListField
        label="User training"
        value={h.user_training}
        onChange={(v) => patch("human_oversight", { user_training: v })}
      />
    </StepGrid>,

    <StepGrid key="security">
      <ListField
        label="Security measures"
        value={c.security_measures}
        onChange={(v) => patch("cybersecurity", { security_measures: v })}
      />
      <TextField
        label="Robustness"
        multiline
        span={2}
        value={c.robustness}
        onChange={(v) => patch("cybersecurity", { robustness: v })}
        hint="Adversarial testing, retraining, and so on."
      />
    </StepGrid>,

    <StepGrid key="logging">
      <BooleanField
        label="Are logs maintained?"
        span="full"
        value={l.logs_maintained}
        onChange={(v) => patch("logging_and_documentation", { logs_maintained: v })}
      />
      <TextField
        label="Retention period"
        value={l.retention_period}
        onChange={(v) => patch("logging_and_documentation", { retention_period: v })}
        hint="For example: 24 months."
      />
      <ListField
        label="Auditability measures"
        span={2}
        value={l.auditability}
        onChange={(v) => patch("logging_and_documentation", { auditability: v })}
      />
    </StepGrid>,

    <StepGrid key="gdpr">
      <BooleanField
        label="Has a GDPR conformity assessment been performed?"
        span="full"
        value={gdpr.assessment_performed}
        onChange={(v) => patch("gdpr_conformity_assessment", { assessment_performed: v })}
      />
      <TextField
        label="Notified body"
        value={gdpr.notified_body}
        onChange={(v) => patch("gdpr_conformity_assessment", { notified_body: v })}
      />
      <TextField
        label="Outcome"
        multiline
        span={2}
        value={gdpr.outcome}
        onChange={(v) => patch("gdpr_conformity_assessment", { outcome: v })}
      />
    </StepGrid>,
  ];

  return (
    <>
      <Dialog
        open={open && !minimised}
        onOpenChange={(next) => {
          // Escape and a click outside put the dialog away rather than close
          // it while a document is being read: closing deletes the record the
          // extraction is writing to.
          if (!next && autofilling) {
            setMinimised(true);
            return;
          }
          // Asks first, then closes , so the dialog stays put until answered.
          if (!next) {
            void requestClose();
            return;
          }
          onOpenChange(next);
        }}
      >
        <DialogContent
          showCloseButton={!autofilling}
          className="flex max-h-[92dvh] w-[95vw] flex-col overflow-y-auto sm:max-w-[min(88rem,95vw)]"
        >
          <DialogHeader>
            <div className="flex items-start justify-between gap-4">
              <div className="flex min-w-0 flex-col gap-2">
                <DialogTitle>{isEditing ? "Edit use case" : "Create a use case"}</DialogTitle>
                <DialogDescription>
                  Upload your documentation to fill this in automatically, or enter the details
                  yourself.
                </DialogDescription>
              </div>
              {/* Takes the close button's place while the read is running: the
                  work carries on, and the app is usable meanwhile. */}
              {autofilling ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                  onClick={() => setMinimised(true)}
                >
                  <Minimize2 />
                  Minimise
                </Button>
              ) : null}
            </div>
          </DialogHeader>

          <Stepper
            steps={steps}
            currentStep={step}
            onStepChange={setStep}
            onReset={requestReset}
            onFinish={finish}
            finishing={saving}
            saveLabel="Save"
            locked={autofilling}
            lockedReason="Reading your document. The fields fill in when it finishes , a moment. You can minimise this and carry on elsewhere."
          >
            {content[step]}
          </Stepper>
        </DialogContent>
      </Dialog>

      {minimised ? (
        <MinimisedRun
          run={autofill}
          title={isEditing ? (editing?.name ?? "Use case") : name.trim() || "New use case"}
          onReopen={() => {
            setMinimised(false);
            // The list page toggles `open`, so it may have been switched off
            // while this was out of the way. Reopening has to put it back.
            if (!open) onOpenChange(true);
          }}
        />
      ) : null}
    </>
  );
}
