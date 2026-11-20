"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export type ConfirmOptions = {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Red confirm button, for anything that deletes or throws work away. */
  destructive?: boolean;
};

type Ask = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = React.createContext<Ask | null>(null);

/**
 * One confirmation dialog for the whole app.
 *
 * `window.confirm` blocks the page, looks nothing like the rest of the app and
 * cannot say much. This is the same idea as a promise: `await confirm({…})`
 * resolves true if the user goes ahead, false if they back out.
 */
export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  // Kept after closing so the dialog still has its words while it animates out.
  const [options, setOptions] = React.useState<ConfirmOptions | null>(null);
  const answer = React.useRef<((confirmed: boolean) => void) | null>(null);

  const ask = React.useCallback<Ask>((next) => {
    // A second question while one is open would strand the first promise.
    answer.current?.(false);
    setOptions(next);
    setOpen(true);
    return new Promise<boolean>((resolve) => {
      answer.current = resolve;
    });
  }, []);

  function settle(confirmed: boolean) {
    setOpen(false);
    answer.current?.(confirmed);
    answer.current = null;
  }

  return (
    <ConfirmContext.Provider value={ask}>
      {children}

      <Dialog
        open={open}
        onOpenChange={(next) => {
          // Escape, the close button and a click outside all mean "no".
          if (!next) settle(false);
        }}
      >
        <DialogContent showCloseButton={false} className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{options?.title}</DialogTitle>
            {options?.description ? (
              <DialogDescription>{options.description}</DialogDescription>
            ) : null}
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => settle(false)}>
              {options?.cancelLabel ?? "Cancel"}
            </Button>
            <Button
              type="button"
              autoFocus
              variant={options?.destructive ? "destructive" : "default"}
              onClick={() => settle(true)}
            >
              {options?.confirmLabel ?? "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
}

/** `const confirm = useConfirm();` then `if (await confirm({ title: … }))`. */
export function useConfirm(): Ask {
  const ask = React.useContext(ConfirmContext);
  if (!ask) throw new Error("useConfirm must be used inside <ConfirmProvider>.");
  return ask;
}
