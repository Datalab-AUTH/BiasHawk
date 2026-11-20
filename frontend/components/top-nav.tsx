"use client";

import Link from "next/link";
import { LogOut, User as UserIcon } from "lucide-react";

import { useSession } from "@/lib/session";
import { resetSelection } from "@/lib/store";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";

export function TopNav() {
  const { user, loading, signOut } = useSession();

  if (loading) return <Skeleton className="ml-auto mr-4 h-8 w-40" />;
  if (!user) return null;

  return (
    <div className="ml-auto flex items-center gap-3 pr-4">
      <span className="hidden text-sm text-muted-foreground sm:inline">{user.email}</span>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="Account menu">
            <UserIcon className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem asChild>
            <Link href="/profile">Profile</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/settings">Settings</Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => {
              // Clear the persisted use case and instance too, so the next
              // person to sign in on this browser does not inherit them.
              resetSelection();
              void signOut();
            }}
          >
            <LogOut className="mr-2 size-4" />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
