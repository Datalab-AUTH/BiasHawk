/**
 * Small additions on top of the shadcn primitives.
 *
 * Button, Card, Input, Label, Badge, Skeleton and friends live in their own
 * files as shadcn generates them; this holds only the handful of composites
 * this app repeats , a labelled field, and the empty / error / loading states.
 */

"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} aria-hidden />;
}

export function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && !error ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      {error ? (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-14 text-center">
      {Icon ? <Icon className="size-7 text-muted-foreground" /> : null}
      <div className="flex flex-col gap-1">
        <p className="font-medium">{title}</p>
        {description ? (
          <p className="max-w-md text-balance text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4">
      <p className="text-sm text-destructive">{message}</p>
      {retry ? (
        <Button size="sm" variant="outline" onClick={retry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}

/** Page title block, used at the top of every dashboard screen. */
export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  breadcrumb?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3">
      {breadcrumb}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
          {description ? (
            <p className="text-balance text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}
