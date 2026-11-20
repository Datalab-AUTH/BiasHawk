"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import { ApiError, auth, ensureCsrfToken } from "@/lib/api";
import type { AllauthConfig } from "@/lib/api";
import { SIGN_UP_ENABLED } from "@/lib/features";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/primitives";

const PROVIDER_LABELS: Record<string, string> = { google: "Google", github: "GitHub" };

/**
 * The providers' own marks.
 *
 * Inlined rather than taken from an icon set: lucide dropped its brand icons,
 * and both companies require their logo, in their colours, on a sign-in button.
 */
function ProviderIcon({ provider }: { provider: string }) {
  if (provider === "google") {
    return (
      <svg viewBox="0 0 18 18" aria-hidden className="size-4 shrink-0">
        <path
          fill="#4285F4"
          d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
        />
        <path
          fill="#34A853"
          d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
        />
        <path
          fill="#FBBC05"
          d="M3.97 10.72a5.41 5.41 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
        />
        <path
          fill="#EA4335"
          d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
        />
      </svg>
    );
  }
  if (provider === "github") {
    return (
      <svg viewBox="0 0 16 16" aria-hidden className="size-4 shrink-0 fill-current">
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
      </svg>
    );
  }
  return null;
}

export function AuthForm({ mode }: { mode: "sign-in" | "sign-up" }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/dashboard/use-cases";
  const oauthError = params.get("error");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(
    oauthError ? "That sign-in could not be completed. Please try again." : null
  );
  const [providers, setProviders] = useState<string[]>([]);
  const [csrf, setCsrf] = useState("");
  const [callbackUrl, setCallbackUrl] = useState("");

  // Only offer the buttons for providers the backend actually has credentials
  // for, rather than showing a button that will fail.
  useEffect(() => {
    auth
      .config()
      .then((config: AllauthConfig) =>
        setProviders((config.data?.socialaccount?.providers ?? []).map((p) => p.id))
      )
      .catch(() => setProviders([]));
  }, []);

  // Starting an OAuth flow is a real form POST, because it ends in a
  // cross-origin redirect that fetch cannot follow. A form cannot set the
  // X-CSRFToken header, so Django needs the token in the body instead ,
  // without it the provider redirect is rejected as "CSRF token missing".
  useEffect(() => {
    void ensureCsrfToken().then(setCsrf);
    setCallbackUrl(window.location.origin + next);
  }, [next]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "sign-up") {
        await auth.signUp(email.trim().toLowerCase(), password);
      } else {
        await auth.signIn(email.trim().toLowerCase(), password);
      }
      router.replace(next);
      router.refresh();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Something went wrong. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

  const isSignUp = mode === "sign-up";

  return (
    <Card className="w-full max-w-sm">
      <CardContent className="flex flex-col gap-5 p-6">
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-semibold tracking-tight">
            {isSignUp ? "Create an account" : "Sign in to BiasHawk"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {isSignUp
              ? "Assess AI systems for bias, data quality and regulatory risk."
              : "Welcome back."}
          </p>
        </div>

        {providers.length > 0 ? (
          <>
            <div className="flex flex-col gap-2">
              {providers.map((provider) => (
                <form key={provider} method="post" action={auth.providerRedirectUrl}>
                  <input type="hidden" name="provider" value={provider} />
                  <input type="hidden" name="process" value="login" />
                  <input type="hidden" name="callback_url" value={callbackUrl} />
                  <input type="hidden" name="csrfmiddlewaretoken" value={csrf} />
                  <Button
                    type="submit"
                    variant="outline"
                    className="w-full"
                    disabled={!csrf || !callbackUrl}
                  >
                    <ProviderIcon provider={provider} />
                    Continue with {PROVIDER_LABELS[provider] ?? provider}
                  </Button>
                </form>
              ))}
            </div>
            <div className="flex items-center gap-3">
              <span className="h-px flex-1 bg-border" />
              <span className="text-xs text-muted-foreground">or</span>
              <span className="h-px flex-1 bg-border" />
            </div>
          </>
        ) : null}

        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </Field>
          <Field
            label="Password"
            htmlFor="password"
            hint={isSignUp ? "At least 8 characters." : undefined}
          >
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete={isSignUp ? "new-password" : "current-password"}
              required
              minLength={isSignUp ? 8 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          <Button type="submit" loading={submitting}>
            {isSignUp ? "Create account" : "Sign in"}
          </Button>
        </form>

        {/* Accounts are made by hand for now, so the page does not invite
            someone to create one it will not give them. */}
        {SIGN_UP_ENABLED || isSignUp ? (
          <p className="text-center text-sm text-muted-foreground">
            {isSignUp ? "Already have an account? " : "No account yet? "}
            <Link
              href={isSignUp ? "/sign-in" : "/sign-up"}
              className="font-medium text-foreground underline underline-offset-4"
            >
              {isSignUp ? "Sign in" : "Create one"}
            </Link>
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
