"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Usecase } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/primitives";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProfilePage() {
  const { user, loading } = useSession();
  const usecases = useQuery({
    queryKey: ["usecases"],
    queryFn: () => api.get<Usecase[]>("/usecases"),
  });

  if (loading) return <Skeleton className="h-48" />;
  if (!user) return null;

  const instances = (usecases.data ?? []).reduce((total, u) => total + u.instance_count, 0);

  return (
    <>
      <PageHeader title="Profile" description="Your account." />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-[minmax(8rem,auto)_1fr]">
              <dt className="text-sm text-muted-foreground">Name</dt>
              <dd className="text-sm">{user.name || ","}</dd>
              <dt className="text-sm text-muted-foreground">Email</dt>
              <dd className="text-sm">{user.email}</dd>
              <dt className="text-sm text-muted-foreground">Member since</dt>
              <dd className="text-sm">{formatDate(user.date_joined)}</dd>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Your work</CardTitle>
          </CardHeader>
          <CardContent>
            {usecases.isLoading ? (
              <Skeleton className="h-16" />
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border px-4 py-3">
                  <p className="text-xs text-muted-foreground">Use cases</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums">
                    {usecases.data?.length ?? 0}
                  </p>
                </div>
                <div className="rounded-md border px-4 py-3">
                  <p className="text-xs text-muted-foreground">Instances</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums">{instances}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
