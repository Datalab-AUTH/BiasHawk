"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

import { resetSelection, useSelection } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/primitives";

type Theme = "light" | "dark" | "system";

const OPTIONS: { value: Theme; label: string; icon: React.ElementType }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

export default function SettingsPage() {
  const [theme, setTheme] = useState<Theme>("system");
  const useCaseName = useSelection((s) => s.selectedUseCaseName);
  const instanceName = useSelection((s) => s.selectedInstanceName);

  useEffect(() => {
    setTheme((localStorage.getItem("biashawk-theme") as Theme) ?? "system");
  }, []);

  function apply(next: Theme) {
    setTheme(next);
    localStorage.setItem("biashawk-theme", next);
    const dark =
      next === "dark" ||
      (next === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
  }

  return (
    <>
      <PageHeader title="Settings" description="How the dashboard behaves on this device." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
          </CardHeader>
          <CardContent className="flex gap-2">
            {OPTIONS.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => apply(value)}
                aria-pressed={theme === value}
                className={cn(
                  "flex flex-1 flex-col items-center gap-2 rounded-md border px-4 py-3 text-sm transition-colors",
                  theme === value
                    ? "border-foreground/40 bg-accent"
                    : "text-muted-foreground hover:border-foreground/20"
                )}
              >
                <Icon className="size-4" aria-hidden />
                {label}
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Current selection</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[minmax(6rem,auto)_1fr]">
              <dt className="text-sm text-muted-foreground">Use case</dt>
              <dd className="text-sm">{useCaseName ?? "None selected"}</dd>
              <dt className="text-sm text-muted-foreground">Instance</dt>
              <dd className="text-sm">{instanceName ?? "None selected"}</dd>
            </dl>
            <Button variant="outline" size="sm" className="w-fit" onClick={resetSelection}>
              Clear selection
            </Button>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
