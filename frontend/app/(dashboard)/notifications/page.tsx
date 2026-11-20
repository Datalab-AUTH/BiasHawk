"use client";

import { PageHeader } from "@/components/ui/primitives";
import { Card, CardContent } from "@/components/ui/card";

export default function Page() {
  return (
    <>
      <PageHeader title="Notifications" description="Alerts about long-running analyses." />
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">In-app notifications are not enabled yet. Analysis progress is shown live in the sidebar and on each analysis page.</CardContent>
      </Card>
    </>
  );
}
