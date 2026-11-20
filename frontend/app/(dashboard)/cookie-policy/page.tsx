"use client";

import { PageHeader } from "@/components/ui/primitives";
import { Card, CardContent } from "@/components/ui/card";

export default function Page() {
  return (
    <>
      <PageHeader title="Cookie Policy" description="How this application uses cookies." />
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">BiasHawk sets two cookies, both strictly necessary: a session cookie that keeps you signed in, and a CSRF token that protects form submissions. No analytics or advertising cookies are used.</CardContent>
      </Card>
    </>
  );
}
