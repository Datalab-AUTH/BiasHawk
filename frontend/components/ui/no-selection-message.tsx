import { Card, CardContent } from "@/components/ui/card";
import { AlertCircle } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function NoSelectionMessage() {
  return (
    <Card className="w-full max-w-2xl mx-auto mt-8">
      <CardContent className="pt-6">
        <div className="flex flex-col items-center justify-center text-center space-y-4 py-8">
          <AlertCircle className="h-12 w-12 text-muted-foreground" />
          <div className="space-y-2">
            <h3 className="text-lg font-semibold">No Use Case or Instance Selected</h3>
            <p className="text-sm text-muted-foreground max-w-md">
              Please select a use case and an instance from the Project Setup page to access this feature.
            </p>
          </div>
          <Link href="/dashboard/use-cases">
            <Button>Go to Project Setup</Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
