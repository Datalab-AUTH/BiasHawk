"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";

import { ApiError, auth } from "@/lib/api";
import { SessionProvider } from "@/lib/session";
import { ConfirmProvider } from "@/components/ui/confirm-dialog";

export function Providers({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [client] = useState(() => {
    /**
     * A session can outlive the account it belongs to , the cookie is still
     * present but the API refuses it. Without this the page renders "could not
     * load" forever, because the cookie gate in proxy.ts sees a session and
     * lets the request through.
     */
    const onUnauthorized = (error: unknown) => {
      if (!(error instanceof ApiError)) return;
      if (error.status !== 401 && error.status !== 403) return;
      if (pathname === "/sign-in" || pathname === "/sign-up") return;

      // The session cookie is httpOnly, so it cannot be dropped from here ,
      // ask the server to clear it, otherwise the cookie gate in proxy.ts keeps
      // waving us back through to a page the API will refuse again.
      void auth.signOut().finally(() => {
        router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
      });
    };

    return new QueryClient({
      queryCache: new QueryCache({ onError: onUnauthorized }),
      mutationCache: new MutationCache({ onError: onUnauthorized }),
      defaultOptions: {
        queries: {
          staleTime: 10_000,
          refetchOnWindowFocus: false,
          retry: (failureCount, error) => {
            // Retrying a 4xx just repeats the same answer.
            if (error instanceof ApiError && error.status < 500) return false;
            return failureCount < 2;
          },
        },
      },
    });
  });

  return (
    <QueryClientProvider client={client}>
      <SessionProvider>
        <ConfirmProvider>{children}</ConfirmProvider>
      </SessionProvider>
      <Toaster position="bottom-right" richColors closeButton />
    </QueryClientProvider>
  );
}
