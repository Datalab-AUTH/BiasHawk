"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api, auth } from "@/lib/api";
import type { User } from "@/lib/types";

type SessionState = {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({
  children,
  initialUser = null,
}: {
  children: React.ReactNode;
  initialUser?: User | null;
}) {
  const [user, setUser] = useState<User | null>(initialUser);
  const [loading, setLoading] = useState(initialUser === null);
  const router = useRouter();

  async function refresh() {
    try {
      setUser(await api.get<User>("/me"));
    } catch (error) {
      // 403 just means "not signed in" , the API has no anonymous access.
      if (error instanceof ApiError && (error.status === 403 || error.status === 401)) {
        setUser(null);
      } else {
        throw error;
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSignOut() {
    await auth.signOut();
    setUser(null);
    router.replace("/sign-in");
  }

  return (
    <SessionContext.Provider value={{ user, loading, refresh, signOut: handleSignOut }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside a SessionProvider.");
  return context;
}
