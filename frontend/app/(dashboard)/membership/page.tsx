"use client";

import { PageHeader } from "@/components/ui/primitives";
import { Card, CardContent } from "@/components/ui/card";

export default function Page() {
  return (
    <>
      <PageHeader title="Membership" description="Your plan and seats." />
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">Membership management is not part of this deployment yet.</CardContent>
      </Card>
    </>
  );
}
