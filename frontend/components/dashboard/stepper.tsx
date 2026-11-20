"use client";

import * as React from "react";
import { Check, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/**
 * The multi-step form shell.
 *
 * Step 0 is always the autofill offer , upload documents and let extraction
 * fill everything in, or continue and type it. Every step after that is one
 * section of the record being built.
 */
export function Stepper({
  steps,
  currentStep,
  onStepChange,
  onReset,
  onFinish,
  finishing = false,
  nextEnabled = true,
  saveLabel = "Save",
  locked = false,
  lockedReason,
  children,
}: {
  steps: { title: string; description?: string }[];
  currentStep: number;
  onStepChange: (step: number) => void;
  onReset: () => void;
  onFinish: () => void;
  finishing?: boolean;
  nextEnabled?: boolean;
  saveLabel?: string;
  /**
   * Blocks every control while a background step is filling the form in.
   * Without it you can walk to a later step, see fields that are still empty,
   * and save that emptiness over the values as they arrive.
   */
  locked?: boolean;
  lockedReason?: string;
  children: React.ReactNode;
}) {
  const isLast = currentStep === steps.length - 1;

  return (
    <div className="flex w-full flex-col">
      <ol className="mb-8 flex flex-col items-center justify-between gap-1 md:flex-row">
        {steps.map((step, index) => (
          <React.Fragment key={step.title}>
            <li className="flex flex-col items-center">
              <span
                aria-current={index === currentStep ? "step" : undefined}
                className={cn(
                  "flex size-6 items-center justify-center rounded-full border-2 text-xs font-medium",
                  index < currentStep
                    ? "border-primary bg-primary text-primary-foreground"
                    : index === currentStep
                      ? "border-primary"
                      : "border-muted text-muted-foreground"
                )}
              >
                {index < currentStep ? (
                  <Check className="size-4" aria-hidden />
                ) : (
                  index + 1
                )}
              </span>
              <span
                className={cn(
                  "mt-2 text-center text-xs font-medium",
                  index === currentStep || index < currentStep
                    ? "text-foreground"
                    : "text-muted-foreground"
                )}
              >
                {step.title}
              </span>
            </li>
            {index < steps.length - 1 ? (
              <ChevronRight
                className="hidden shrink-0 text-muted-foreground md:block"
                aria-hidden
              />
            ) : null}
          </React.Fragment>
        ))}
      </ol>

      {steps[currentStep]?.description ? (
        <p className="mb-4 text-sm text-muted-foreground">{steps[currentStep].description}</p>
      ) : null}

      {/* A disabled fieldset takes every control inside it with it, so the
          fields of the step being shown are read-only while a background step
          is filling them in , not just the buttons below. */}
      <fieldset
        disabled={locked}
        aria-busy={locked || undefined}
        className={cn("min-h-[18rem] min-w-0", locked && "opacity-60")}
      >
        {children}
      </fieldset>

      {locked && lockedReason ? (
        <p className="mt-4 rounded-md border border-dashed px-3 py-2 text-center text-xs text-muted-foreground">
          {lockedReason}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-6">
        <Button
          type="button"
          variant="outline"
          onClick={() => onStepChange(currentStep - 1)}
          disabled={locked}
          className={currentStep === 0 ? "invisible" : undefined}
        >
          Previous
        </Button>

        <div className="flex items-center gap-2">
          {/* Save is available from every step: the steps are one record, not a
              wizard that has to be completed in order, and walking to the end
              just to keep an edit made on step 2 is busywork. It carries the
              same weight as Continue and Next, so it is the same solid button:
              a grey one beside them read as "not the real action". */}
          <Button type="button" onClick={onFinish} loading={finishing} disabled={locked}>
            {saveLabel}
          </Button>

          {!isLast ? (
            <Button
              type="button"
              onClick={() => onStepChange(currentStep + 1)}
              disabled={!nextEnabled || locked}
            >
              {steps[currentStep]?.title === "Autofill" ? "Continue" : "Next"}
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex justify-start pt-3">
        <Button type="button" variant="ghost" size="sm" onClick={onReset} disabled={locked}>
          Reset all fields
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------- fields --- */

/**
 * How wide a field sits in `StepGrid`.
 *
 * The grid is three columns on a wide screen, so a field is either one of
 * them, two, or the whole row. Nothing sizes itself: a step reads as a table
 * because every field lines up with the ones above and below it.
 */
type Span = 1 | 2 | "full";

const SPAN_CLASS: Record<Span, string> = {
  1: "",
  2: "md:col-span-2",
  full: "md:col-span-2 xl:col-span-3",
};

/**
 * One labelled field.
 *
 * Label, control and hint each keep the same height whether or not they have
 * anything in them, so fields side by side in a row start and end together
 * instead of drifting by a few pixels wherever a hint happens to be.
 */
export function TextField({
  label,
  value,
  onChange,
  placeholder,
  hint,
  multiline,
  span = 1,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: string;
  multiline?: boolean;
  span?: Span;
}) {
  const id = React.useId();
  const Control = multiline ? "textarea" : "input";
  return (
    <div className={cn("flex min-w-0 flex-col", SPAN_CLASS[span])}>
      <label htmlFor={id} className="mb-1.5 flex min-h-5 items-end text-sm font-medium leading-5">
        {label}
      </label>
      <Control
        id={id}
        value={value}
        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
          onChange(e.target.value)
        }
        placeholder={placeholder}
        className={cn(
          "w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-xs transition-colors",
          "placeholder:text-muted-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
          "disabled:cursor-not-allowed disabled:opacity-70",
          multiline ? "min-h-28 resize-y leading-6" : "h-9"
        )}
      />
      {/* Always rendered: an empty hint on one field would otherwise make the
          next row start higher than its neighbour's. */}
      <p className="mt-1.5 min-h-4 text-xs leading-4 text-muted-foreground">{hint ?? ""}</p>
    </div>
  );
}

/** A string[] field, edited as one item per line. */
export function ListField({
  label,
  value,
  onChange,
  hint,
  span = 1,
}: {
  label: string;
  value: string[];
  onChange: (value: string[]) => void;
  hint?: string;
  span?: Span;
}) {
  return (
    <TextField
      label={label}
      multiline
      span={span}
      value={(value ?? []).join("\n")}
      onChange={(text) =>
        onChange(
          text
            .split("\n")
            .map((line) => line.trim())
            .filter(Boolean)
        )
      }
      hint={hint ?? "One per line."}
    />
  );
}

export function BooleanField({
  label,
  value,
  onChange,
  hint,
  span = "full",
}: {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  hint?: string;
  span?: Span;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col", SPAN_CLASS[span])}>
      {/* Sits on the label row of its neighbours, so a yes/no in a row of text
          fields does not float half a line above them. */}
      <span className="mb-1.5 min-h-5 leading-5" aria-hidden />
      <div className="flex min-h-9 items-center justify-between gap-4 rounded-md border border-input bg-background px-3 py-1.5 shadow-xs">
        <span className="text-sm font-medium">{label}</span>
        <div className="flex shrink-0 gap-1">
          {[true, false].map((option) => (
            <button
              key={String(option)}
              type="button"
              aria-pressed={value === option}
              onClick={() => onChange(option)}
              className={cn(
                "rounded-md px-3 py-1 text-xs transition-colors",
                value === option
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent"
              )}
            >
              {option ? "Yes" : "No"}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1.5 min-h-4 text-xs leading-4 text-muted-foreground">{hint ?? ""}</p>
    </div>
  );
}

/**
 * The one grid every step lays its fields out on.
 *
 * A step puts its single-line fields in first and its boxes after, so each row
 * holds controls of the same height and the step reads as rows rather than as
 * a pile of differently sized cards.
 */
export function StepGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 items-start gap-x-6 gap-y-1 md:grid-cols-2 xl:grid-cols-3">
      {children}
    </div>
  );
}

/** A titled band of fields, for steps that hold more than one idea. */
export function StepSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5 border-b pb-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
