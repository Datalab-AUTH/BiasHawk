"use client";

import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/primitives";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

/**
 * The bias assessment needs three things the dataset cannot supply on its own:
 * which column is the outcome, which of its values counts as favourable, and
 * which columns are sensitive.
 *
 * All three are chosen on the page rather than in a dialog behind the Run
 * button: they are the setup, not a confirmation step, and they stay readable
 * and editable between runs.
 */

/**
 * The same bar the assessment applies in core.analysis.bias: a feature is
 * compared by grouping rows on its distinct values, so a column with a value
 * per row has nothing to compare. Kept in step with MAX_GROUP_VALUES and
 * MIN_ROWS_PER_GROUP there.
 */
export const MAX_GROUP_VALUES = 50;
export const MIN_ROWS_PER_GROUP = 10;

/**
 * Columns that cannot be grouped on, mapped to why not.
 *
 * A dataset uploaded before the API measured its shape has no profile; those
 * columns are left selectable rather than blocked on a guess, and the
 * assessment still leaves them out of the comparisons.
 */
export function ungroupableColumns(
  profile: { rows: number; distinct: Record<string, number> } | undefined
): Record<string, string> {
  if (!profile?.distinct) return {};
  const blocked: Record<string, string> = {};
  for (const [column, distinct] of Object.entries(profile.distinct)) {
    const perGroup = distinct ? profile.rows / distinct : 0;
    if (distinct > MAX_GROUP_VALUES) {
      blocked[column] =
        `${distinct} distinct values across ${profile.rows} rows. ` +
        `Over ${MAX_GROUP_VALUES} groups cannot be compared; band it into ranges first.`;
    } else if (perGroup < MIN_ROWS_PER_GROUP) {
      blocked[column] =
        `${distinct} distinct values across ${profile.rows} rows, about ` +
        `${perGroup.toFixed(1)} rows each. Groups need at least ${MIN_ROWS_PER_GROUP} rows to compare.`;
    }
  }
  return blocked;
}

/**
 * Which columns fairness is measured across.
 *
 * The choice is the user's. Detection only marks its suggestions here and
 * seeds the selection until the user picks for themselves, so an instance
 * where nobody ran the detector is just as workable as one where they did.
 */
export function SensitiveFeaturePicker({
  columns,
  selected,
  detected,
  onToggle,
  onUseDetected,
  ungroupable = {},
  disabled = false,
}: {
  columns: string[];
  selected: string[];
  /** What the detector suggested, if it has run. */
  detected: string[];
  onToggle: (column: string) => void;
  /** Offered once the user's own picks differ from the suggestions. */
  onUseDetected?: () => void;
  /** Columns that cannot be compared, mapped to why not. */
  ungroupable?: Record<string, string>;
  disabled?: boolean;
}) {
  const blocked = Object.entries(ungroupable).filter(([column]) => columns.includes(column));
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Pick the columns to measure fairness across. Choose them yourself, or run the detector
          below and adjust what it suggests.
        </p>
        {onUseDetected ? (
          <button
            type="button"
            onClick={onUseDetected}
            className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            Reset to detected
          </button>
        ) : null}
      </div>

      {columns.length ? (
        <div className="flex flex-wrap gap-1.5">
          {columns.map((column) => {
            const active = selected.includes(column);
            const suggested = detected.includes(column);
            const reason = ungroupable[column];
            return (
              <button
                key={column}
                type="button"
                aria-pressed={active}
                aria-disabled={Boolean(reason) || undefined}
                disabled={disabled || Boolean(reason)}
                onClick={() => onToggle(column)}
                title={reason ?? (suggested ? "Suggested by the detector" : undefined)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs transition-colors",
                  "disabled:cursor-not-allowed disabled:opacity-50",
                  reason && "line-through",
                  active
                    ? "border-transparent bg-primary text-primary-foreground"
                    : "border-border text-muted-foreground hover:border-foreground/30"
                )}
              >
                {suggested ? (
                  <span
                    aria-hidden
                    className={cn(
                      "size-1.5 rounded-full",
                      active ? "bg-primary-foreground/70" : "bg-amber-500"
                    )}
                  />
                ) : null}
                {column}
              </button>
            );
          })}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          The dataset has no columns to choose from yet.
        </p>
      )}

      <p className="text-xs text-muted-foreground">
        {selected.length
          ? `${selected.length} selected. A dot marks a column the detector suggested.`
          : "Select at least one column. Nothing can be measured without one."}
      </p>

      {/* Said here rather than left for the report: a column with a value per
          row produces a group per row, and nothing to compare between them. */}
      {blocked.length ? (
        <div className="rounded-md bg-amber-500/10 px-3 py-2">
          <p className="text-xs font-medium text-amber-700">
            {blocked.length === 1
              ? "One column cannot be compared and is not selectable:"
              : `${blocked.length} columns cannot be compared and are not selectable:`}
          </p>
          <ul className="mt-1 flex flex-col gap-0.5">
            {blocked.map(([column, reason]) => (
              <li key={column} className="text-xs text-amber-700">
                <span className="font-mono">{column}</span>: {reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/** The outcome the model predicts, and which of its values is the good one. */
export function BiasTargetFields({
  columns,
  label,
  favorable,
  onLabelChange,
  onFavorableChange,
}: {
  columns: string[];
  label: string;
  favorable: string;
  onLabelChange: (column: string) => void;
  onFavorableChange: (value: string) => void;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Field label="Target column" htmlFor="bias-label" hint="The outcome the model predicts.">
        <Select value={label || undefined} onValueChange={onLabelChange}>
          <SelectTrigger id="bias-label" className="w-full">
            <SelectValue placeholder="Choose a column" />
          </SelectTrigger>
          <SelectContent>
            {columns.map((column) => (
              <SelectItem key={column} value={column}>
                {column}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field
        label="Favourable outcome"
        htmlFor="bias-favorable"
        hint='The value in that column that counts as a good result: "good", "1", "approved".'
      >
        <Input
          id="bias-favorable"
          value={favorable}
          onChange={(event) => onFavorableChange(event.target.value)}
          placeholder="good"
        />
      </Field>
    </div>
  );
}
