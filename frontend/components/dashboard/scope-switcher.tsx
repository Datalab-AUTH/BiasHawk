"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";

import { api } from "@/lib/api";
import { useSelection } from "@/lib/store";
import type { Instance, Usecase } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * Use case and instance pickers, at the top of the sidebar.
 *
 * Everything below them is scoped to this choice, so it belongs where it is
 * always visible rather than buried on a page you have to scroll to find.
 */
export function ScopeSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const useCaseId = useSelection((s) => s.selectedUseCaseId);
  const instanceId = useSelection((s) => s.selectedInstanceId);
  const setUseCase = useSelection((s) => s.setUseCase);
  const setInstance = useSelection((s) => s.setInstance);

  // Whether the page open right now is this use case's own overview page, or
  // this instance's , not any page nested under them, those already have
  // their own nav item lit up below. Exact paths, so exactly one of the two
  // can ever match.
  const useCasePath = useCaseId ? `/dashboard/use-cases/${useCaseId}` : null;
  const instancePath =
    useCaseId && instanceId ? `${useCasePath}/instances/${instanceId}` : null;
  const onUseCasePage = Boolean(useCasePath && pathname === useCasePath);
  const onInstancePage = Boolean(instancePath && pathname === instancePath);

  const usecases = useQuery({
    queryKey: ["usecases"],
    queryFn: () => api.get<Usecase[]>("/usecases"),
  });

  const instances = useQuery({
    queryKey: ["instances", useCaseId],
    enabled: Boolean(useCaseId),
    queryFn: () => api.get<Instance[]>(`/instances?usecase=${useCaseId}`),
  });

  // The selection is persisted in localStorage, so it outlives the account that
  // made it , signing in as someone else, or deleting the use case, leaves an
  // id pointing at something this user cannot see. Drop it once the real list
  // arrives, otherwise the analysis links stay enabled and lead to a 404.
  useEffect(() => {
    if (!useCaseId || !usecases.data) return;
    if (!usecases.data.some((u) => u.id === useCaseId)) setUseCase(null);
  }, [useCaseId, usecases.data, setUseCase]);

  useEffect(() => {
    if (!instanceId || !instances.data) return;
    if (!instances.data.some((i) => i.id === instanceId)) setInstance(null);
  }, [instanceId, instances.data, setInstance]);

  function chooseUseCase(id: string) {
    const chosen = usecases.data?.find((u) => u.id === id);
    setUseCase(id || null, chosen?.name ?? null);
    if (id) router.push(`/dashboard/use-cases/${id}`);
  }

  function chooseInstance(id: string) {
    const chosen = instances.data?.find((i) => i.id === id);
    setInstance(id || null, chosen?.name ?? null);
    if (id && useCaseId) {
      router.push(`/dashboard/use-cases/${useCaseId}/instances/${id}`);
    }
  }

  return (
    <div className="flex flex-col gap-2 px-2 pb-1">
      <Picker
        label="Use case"
        value={useCaseId ?? ""}
        placeholder={usecases.isLoading ? "Loading…" : "Select a use case"}
        options={(usecases.data ?? []).map((u) => ({ value: u.id, label: u.name }))}
        onChange={chooseUseCase}
        active={onUseCasePage}
        onNavigate={
          useCaseId ? () => router.push(`/dashboard/use-cases/${useCaseId}`) : undefined
        }
        navigateLabel="Open use case"
      />
      <Picker
        label="Instance"
        value={instanceId ?? ""}
        placeholder={
          !useCaseId
            ? "Select a use case first"
            : instances.isLoading
              ? "Loading…"
              : (instances.data?.length ?? 0) === 0
                ? "No instances yet"
                : "Select an instance"
        }
        options={(instances.data ?? []).map((i) => ({ value: i.id, label: i.name }))}
        onChange={chooseInstance}
        disabled={!useCaseId || (instances.data?.length ?? 0) === 0}
        active={onInstancePage}
        onNavigate={
          useCaseId && instanceId
            ? () => router.push(`/dashboard/use-cases/${useCaseId}/instances/${instanceId}`)
            : undefined
        }
        navigateLabel="Open instance"
      />
    </div>
  );
}

function Picker({
  label,
  value,
  placeholder,
  options,
  onChange,
  disabled,
  active,
  onNavigate,
  navigateLabel,
}: {
  label: string;
  value: string;
  placeholder: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** The page open right now is this item's, so the picker should look selected. */
  active?: boolean;
  /** Jumps straight into the currently selected item's page. Omitted when nothing is selected. */
  onNavigate?: () => void;
  navigateLabel?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="px-1 text-[0.6875rem] font-medium uppercase tracking-wide text-sidebar-foreground/60">
        {label}
      </span>
      <div className="flex items-center gap-1">
        <Select value={value || undefined} onValueChange={onChange} disabled={disabled}>
          <SelectTrigger
            aria-label={label}
            size="sm"
            className={cn(
              "h-8 min-w-0 flex-1 border-sidebar-border bg-sidebar-accent/60 text-sidebar-foreground",
              "focus-visible:ring-sidebar-ring",
              "disabled:cursor-not-allowed disabled:opacity-60",
              active && "border-sidebar-primary"
            )}
          >
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {options.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {onNavigate ? (
          <button
            type="button"
            onClick={onNavigate}
            aria-label={navigateLabel}
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-md border border-sidebar-border",
              "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring"
            )}
          >
            <ArrowRight className="size-3.5" aria-hidden />
          </button>
        ) : null}
      </div>
    </div>
  );
}
