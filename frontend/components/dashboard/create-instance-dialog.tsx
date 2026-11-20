"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { useSelection } from "@/lib/store";
import type { AIDataComplianceForm, Instance } from "@/lib/types";
import { Minimize2 } from "lucide-react";
import { toast as notify } from "sonner";

import {
  AutofillStep,
  MinimisedRun,
  useAutofillRun,
} from "@/components/dashboard/autofill-step";
import { InstanceDataset } from "@/components/dashboard/instance-dataset";
import {
  BooleanField,
  ListField,
  StepGrid,
  Stepper,
  TextField,
} from "@/components/dashboard/stepper";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const UNKNOWN = "unknown";

function emptyForm(): AIDataComplianceForm {
  return {
    Data_Overview: {
      Data_Use_Description: "",
      Types_of_Data_Used: [],
      Sources_of_Data: "",
      Purpose_of_Data_Use: "",
      High_Risk_Data_Handling: false,
    },
    Data_Collection_and_Origin: {
      Data_Collected_From: [],
      Consent_Mechanism_Documented: false,
      Anonymization_or_Pseudonymization_Applied: false,
      Sensitive_Data_Included: false,
    },
    Data_Quality_Assurance: {
      Data_Cleaning_Steps: [],
      Missing_Data_Handling: "",
      Duplication_Removal: "",
      Preprocessing_Methods: [],
      Validation_Methods: "",
    },
    Data_Management_and_Governance: {
      Data_Retention_Policy: "",
      Access_Control_Mechanisms: [],
      Data_Lineage_and_Provenance_Tracking: false,
      Data_Minimization_Measures: [],
      Storage_Location_and_Jurisdiction: "",
      Compliance_with_GDPR: false,
    },
    Monitoring_and_Updates: {
      Frequency_of_Data_Updates: "",
      User_Feedback_Integrated_into_Data_Updates: false,
    },
  };
}

/** Extraction writes "unknown" into gaps; blank them so they read as unfilled. */
function blankUnknowns(form: AIDataComplianceForm): AIDataComplianceForm {
  const clean = (v: unknown) =>
    typeof v === "string" && v.trim().toLowerCase() === UNKNOWN ? "" : ((v as string) ?? "");
  const cleanList = (v: string[]) =>
    (v ?? []).filter((item) => item?.trim().toLowerCase() !== UNKNOWN);

  const walk = <T extends Record<string, unknown>>(section: T): T =>
    Object.fromEntries(
      Object.entries(section).map(([key, value]) => [
        key,
        Array.isArray(value)
          ? cleanList(value as string[])
          : typeof value === "string"
            ? clean(value)
            : value,
      ])
    ) as T;

  return {
    Data_Overview: walk(form.Data_Overview),
    Data_Collection_and_Origin: walk(form.Data_Collection_and_Origin),
    Data_Quality_Assurance: walk(form.Data_Quality_Assurance),
    Data_Management_and_Governance: walk(form.Data_Management_and_Governance),
    Monitoring_and_Updates: walk(form.Monitoring_and_Updates),
  };
}

/**
 * Everything the Save button would write, as one comparable string.
 *
 * Closing only asks for confirmation when this differs from what the dialog
 * opened with , leaving without having changed anything loses nothing, so it
 * has nothing to ask about.
 */
function snapshot(name: string, description: string, form: AIDataComplianceForm) {
  return JSON.stringify({ name: name.trim(), description: description.trim(), form });
}

export function CreateInstanceDialog({
  usecaseId,
  open,
  onOpenChange,
  /** Pass an existing instance to edit it instead of creating a new one. */
  editing,
}: {
  usecaseId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing?: Instance | null;
}) {
  const isEditing = Boolean(editing);
  const queryClient = useQueryClient();
  const confirm = useConfirm();
  const setInstance = useSelection((s) => s.setInstance);

  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [form, setForm] = useState<AIDataComplianceForm>(emptyForm);
  const [instanceId, setInstanceId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Put out of the way while a document is being read, rather than closed ,
  // closing throws the half-built record away, and the read is still going.
  const [minimised, setMinimised] = useState(false);
  // What the form held when it opened, to tell an edit from an idle look.
  const baseline = useRef(snapshot("", "", emptyForm()));

  // The run is held here rather than in the step so that unmounting the step
  // , which the dialog does whenever it closes , cannot lose track of it.
  const autofill = useAutofillRun({
    scope: "instances",
    ensureScopeId: ensureRecord,
    extractKind: "instance_extract",
    onExtracted: loadExtracted,
  });
  // True while a document is being read; the whole dialog is locked meanwhile.
  const autofilling = autofill.busy;

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
      notify.success("Your document has been read. Reopen the instance to review the details.");
    } else {
      notify.error(autofill.error ?? "Could not read that document.");
    }
  }, [minimised, autofill.phase, autofill.error]);

  /**
   * Create the record only when something needs it to exist , uploading a
   * document. The manual path creates it once, at Finish. Nothing is written
   * to the database for a dialog the user opens and closes again.
   */
  async function ensureRecord(): Promise<string> {
    if (instanceId) return instanceId;
    const created = await api.post<Instance>("/instances", { usecase: usecaseId, name: "Untitled instance" });
    setInstanceId(created.id);
    return created.id;
  }

  // Load whatever is being edited each time the dialog opens, so reopening
  // after a change shows the current values rather than the ones from before.
  useEffect(() => {
    if (!open) return;
    if (editing) {
      const loaded =
        "Data_Overview" in (editing.metadata ?? {})
          ? blankUnknowns(editing.metadata as never)
          : emptyForm();
      const loadedName = editing.name === "Untitled instance" ? "" : editing.name;
      const loadedDescription = editing.description ?? "";
      setForm(loaded);
      setName(loadedName);
      setDescription(loadedDescription);
      setInstanceId(editing.id);
      baseline.current = snapshot(loadedName, loadedDescription, loaded);
    }
  }, [open, editing]);

  function reset() {
    setStep(0);
    setName("");
    setDescription("");
    setForm(emptyForm());
    setMinimised(false);
    baseline.current = snapshot("", "", emptyForm());
    // The run's "details filled in" note describes values that just went away.
    autofill.reset();
  }

  async function discard() {
    // Closing an edit dialog must not delete the thing being edited , only a
    // half-finished creation is thrown away.
    if (isEditing) {
      setInstanceId(null);
      reset();
      return;
    }
    if (instanceId) await api.delete(`/instances/${instanceId}`).catch(() => null);
    setInstanceId(null);
    reset();
    void queryClient.invalidateQueries({ queryKey: ["instances", usecaseId] });
  }

  /** Is there anything closing would throw away? */
  function dirty() {
    // A record created for an upload is deleted on close, typed into or not.
    if (!isEditing && instanceId) return true;
    return snapshot(name, description, form) !== baseline.current;
  }

  async function requestClose() {
    if (dirty()) {
      const ok = await confirm({
        title: isEditing ? "Close without saving?" : "Discard this instance?",
        description: isEditing
          ? "Anything you changed since opening this is lost. The instance itself stays as it was."
          : "The instance you started is deleted, along with any document uploaded to it.",
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
    const target = id ?? instanceId;
    if (!target) return;
    const instance = await api.get<Instance>(`/instances/${target}`);
    const metadata = instance.metadata as AIDataComplianceForm;
    if (metadata && "Data_Overview" in metadata) {
      const cleaned = blankUnknowns(metadata);
      const filledDescription = description || cleaned.Data_Overview.Data_Use_Description || "";
      setForm(cleaned);
      if (!description) setDescription(filledDescription);
      // These came from the record itself, so they are not unsaved edits.
      baseline.current = snapshot(name, filledDescription, cleaned);
    }
  }

  async function finish() {
    const ok = await confirm({
      title: isEditing ? "Save these changes?" : "Create this instance?",
      description: isEditing
        ? "The details you entered replace what is on the instance now."
        : "The instance is created with the details you entered. You can edit them afterwards.",
      confirmLabel: isEditing ? "Save changes" : "Create instance",
    });
    if (!ok) return;

    setSaving(true);
    try {
      const body = {
        usecase: usecaseId,
        name: name.trim() || "Untitled instance",
        description: description.trim(),
        metadata: form,
      };
      // The manual path never created a record, so Finish is the create.
      const saved = instanceId
        ? await api.patch<Instance>(`/instances/${instanceId}`, body)
        : await api.post<Instance>("/instances", body);
      toast.success(isEditing ? "Instance updated." : "Instance created.");
      setInstance(saved.id, saved.name);
      void queryClient.invalidateQueries({ queryKey: ["instances", usecaseId] });
      setInstanceId(null);
      reset();
      onOpenChange(false);
    } catch {
      toast.error("Could not save the instance.");
    } finally {
      setSaving(false);
    }
  }

  const o = form.Data_Overview;
  const col = form.Data_Collection_and_Origin;
  const q = form.Data_Quality_Assurance;
  const gov = form.Data_Management_and_Governance;
  const mon = form.Monitoring_and_Updates;

  const patch = <K extends keyof AIDataComplianceForm>(
    section: K,
    changes: Partial<AIDataComplianceForm[K]>
  ) => setForm((prev) => ({ ...prev, [section]: { ...prev[section], ...changes } }));

  const steps = [
    { title: "Autofill", description: "Fill in the details by uploading your data documentation." },
    { title: "Dataset", description: "The CSV this instance analyses." },
    { title: "Overview", description: "What the data is and what it is used for." },
    { title: "Origin", description: "Where the data came from, and on what basis." },
    { title: "Quality", description: "How the data is cleaned and validated." },
    { title: "Governance", description: "How the data is retained, secured and minimised." },
    { title: "Monitoring", description: "How often it changes." },
  ];

  const content = [
    <AutofillStep key="autofill" run={autofill} scope="instances" scopeId={instanceId} />,

    <Card key="dataset">
      <CardHeader>
        <CardTitle>Which dataset does this instance analyse?</CardTitle>
        <CardDescription>
          An instance is one dataset to analyse, so upload the CSV it stands for. Data
          governance, quality, bias and drift all read this file , without it there is nothing
          for them to run on. You can also add it later from the instance page.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <InstanceDataset
          instanceId={instanceId}
          ensureInstanceId={ensureRecord}
          disabled={autofilling}
        />
      </CardContent>
    </Card>,

    <StepGrid key="overview">
      <TextField
        label="Instance name"
        value={name}
        onChange={setName}
        hint="For example: Q1 2026 applications."
      />
      <TextField
        label="Sources of data"
        value={o.Sources_of_Data}
        onChange={(v) => patch("Data_Overview", { Sources_of_Data: v })}
      />
      <TextField
        label="Purpose of data use"
        value={o.Purpose_of_Data_Use}
        onChange={(v) => patch("Data_Overview", { Purpose_of_Data_Use: v })}
      />
      <BooleanField
        label="Is the data handling high-risk?"
        span="full"
        value={o.High_Risk_Data_Handling}
        onChange={(v) => patch("Data_Overview", { High_Risk_Data_Handling: v })}
      />
      <TextField
        label="How the data is used"
        multiline
        span={2}
        value={o.Data_Use_Description}
        onChange={(v) => patch("Data_Overview", { Data_Use_Description: v })}
      />
      <ListField
        label="Types of data used"
        value={o.Types_of_Data_Used}
        onChange={(v) => patch("Data_Overview", { Types_of_Data_Used: v })}
      />
      <TextField
        label="Short description"
        multiline
        span="full"
        value={description}
        onChange={setDescription}
        hint="A sentence or two on what this dataset is."
      />
    </StepGrid>,

    <StepGrid key="origin">
      <BooleanField
        label="Is the consent mechanism documented?"
        span={1}
        value={col.Consent_Mechanism_Documented}
        onChange={(v) => patch("Data_Collection_and_Origin", { Consent_Mechanism_Documented: v })}
      />
      <BooleanField
        label="Is anonymisation or pseudonymisation applied?"
        span={1}
        value={col.Anonymization_or_Pseudonymization_Applied}
        onChange={(v) =>
          patch("Data_Collection_and_Origin", { Anonymization_or_Pseudonymization_Applied: v })
        }
      />
      <BooleanField
        label="Does it include sensitive data?"
        span={1}
        value={col.Sensitive_Data_Included}
        onChange={(v) => patch("Data_Collection_and_Origin", { Sensitive_Data_Included: v })}
      />
      <ListField
        label="Data collected from"
        span={2}
        value={col.Data_Collected_From}
        onChange={(v) => patch("Data_Collection_and_Origin", { Data_Collected_From: v })}
      />
    </StepGrid>,

    <StepGrid key="quality">
      <ListField
        label="Cleaning steps"
        value={q.Data_Cleaning_Steps}
        onChange={(v) => patch("Data_Quality_Assurance", { Data_Cleaning_Steps: v })}
      />
      <ListField
        label="Preprocessing methods"
        value={q.Preprocessing_Methods}
        onChange={(v) => patch("Data_Quality_Assurance", { Preprocessing_Methods: v })}
      />
      <TextField
        label="Missing data handling"
        multiline
        value={q.Missing_Data_Handling}
        onChange={(v) => patch("Data_Quality_Assurance", { Missing_Data_Handling: v })}
      />
      <TextField
        label="Duplicate removal"
        multiline
        value={q.Duplication_Removal}
        onChange={(v) => patch("Data_Quality_Assurance", { Duplication_Removal: v })}
      />
      <TextField
        label="Validation methods"
        multiline
        span={2}
        value={q.Validation_Methods}
        onChange={(v) => patch("Data_Quality_Assurance", { Validation_Methods: v })}
      />
    </StepGrid>,

    <StepGrid key="governance">
      <BooleanField
        label="Is data lineage and provenance tracked?"
        span={1}
        value={gov.Data_Lineage_and_Provenance_Tracking}
        onChange={(v) =>
          patch("Data_Management_and_Governance", { Data_Lineage_and_Provenance_Tracking: v })
        }
      />
      <BooleanField
        label="Is the system GDPR compliant?"
        span={1}
        value={gov.Compliance_with_GDPR}
        onChange={(v) => patch("Data_Management_and_Governance", { Compliance_with_GDPR: v })}
      />
      <TextField
        label="Retention policy"
        multiline
        value={gov.Data_Retention_Policy}
        onChange={(v) => patch("Data_Management_and_Governance", { Data_Retention_Policy: v })}
      />
      <TextField
        label="Storage location and jurisdiction"
        multiline
        value={gov.Storage_Location_and_Jurisdiction}
        onChange={(v) =>
          patch("Data_Management_and_Governance", { Storage_Location_and_Jurisdiction: v })
        }
      />
      <ListField
        label="Access control mechanisms"
        value={gov.Access_Control_Mechanisms}
        onChange={(v) => patch("Data_Management_and_Governance", { Access_Control_Mechanisms: v })}
      />
      <ListField
        label="Data minimisation measures"
        value={gov.Data_Minimization_Measures}
        onChange={(v) => patch("Data_Management_and_Governance", { Data_Minimization_Measures: v })}
      />
    </StepGrid>,

    <StepGrid key="monitoring">
      <TextField
        label="How often is the data updated?"
        value={mon.Frequency_of_Data_Updates}
        onChange={(v) => patch("Monitoring_and_Updates", { Frequency_of_Data_Updates: v })}
        hint="For example: monthly."
      />
      <BooleanField
        label="Is user feedback integrated into data updates?"
        span={2}
        value={mon.User_Feedback_Integrated_into_Data_Updates}
        onChange={(v) =>
          patch("Monitoring_and_Updates", { User_Feedback_Integrated_into_Data_Updates: v })
        }
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
                <DialogTitle>{isEditing ? "Edit instance" : "Create an instance"}</DialogTitle>
                <DialogDescription>
                  Upload your data documentation to fill this in automatically, or enter the
                  details yourself.
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
            saveLabel={isEditing ? "Save" : "Create instance"}
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
          title={isEditing ? (editing?.name ?? "Instance") : name.trim() || "New instance"}
          onReopen={() => {
            setMinimised(false);
            // The page toggles `open`, so it may have been switched off while
            // this was out of the way. Reopening has to put it back.
            if (!open) onOpenChange(true);
          }}
        />
      ) : null}
    </>
  );
}
