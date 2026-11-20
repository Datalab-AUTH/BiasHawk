import { Suspense } from "react";
import { redirect } from "next/navigation";
import type { Metadata } from "next";

import { SIGN_UP_ENABLED } from "@/lib/features";
import { AuthForm } from "@/components/auth-form";

export const metadata: Metadata = { title: "Create an account , BiasHawk" };

export default function SignUpPage() {
  // Nothing links here while sign-up is off, but a bookmark or a typed URL
  // would otherwise reach a form that is not on offer.
  if (!SIGN_UP_ENABLED) redirect("/sign-in");

  return (
    <Suspense>
      <AuthForm mode="sign-up" />
    </Suspense>
  );
}
