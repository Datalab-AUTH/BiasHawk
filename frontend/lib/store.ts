import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * The currently selected use case and instance.
 *
 * The sidebar's analysis links are contextual , they point at whichever
 * instance is selected , so the selection has to outlive a page navigation.
 *
 * IDs are UUID strings. The old store typed them `number | null`, which never
 * matched the UUIDs the API actually returns.
 */

type Selection = {
  selectedUseCaseId: string | null;
  selectedUseCaseName: string | null;
  selectedInstanceId: string | null;
  selectedInstanceName: string | null;
  hasHydrated: boolean;
  setUseCase: (id: string | null, name?: string | null) => void;
  setInstance: (id: string | null, name?: string | null) => void;
  setHasHydrated: (value: boolean) => void;
  reset: () => void;
};

const EMPTY = {
  selectedUseCaseId: null,
  selectedUseCaseName: null,
  selectedInstanceId: null,
  selectedInstanceName: null,
};

export const useSelection = create<Selection>()(
  persist(
    (set) => ({
      ...EMPTY,
      hasHydrated: false,

      // Changing use case clears the instance: an instance belonging to a
      // different use case would produce links to a page the API refuses.
      setUseCase: (id, name = null) =>
        set((state) =>
          state.selectedUseCaseId === id
            ? {
                selectedUseCaseId: id,
                selectedUseCaseName: name ?? state.selectedUseCaseName,
              }
            : { ...EMPTY, selectedUseCaseId: id, selectedUseCaseName: name }
        ),

      setInstance: (id, name = null) =>
        set({ selectedInstanceId: id, selectedInstanceName: name }),

      setHasHydrated: (value) => set({ hasHydrated: value }),
      reset: () => set(EMPTY),
    }),
    {
      name: "biashawk-selection",
      // Persist only the selection, never the hydration flag , otherwise a
      // stored `true` would defeat the check it exists for.
      partialize: (state) => ({
        selectedUseCaseId: state.selectedUseCaseId,
        selectedUseCaseName: state.selectedUseCaseName,
        selectedInstanceId: state.selectedInstanceId,
        selectedInstanceName: state.selectedInstanceName,
      }),
      onRehydrateStorage: () => (state) => state?.setHasHydrated(true),
    }
  )
);

export function resetSelection() {
  useSelection.getState().reset();
  if (typeof localStorage !== "undefined") localStorage.removeItem("biashawk-selection");
}

/**
 * The records a running autofill is writing into.
 *
 * The create dialog can be minimised while a document is being read, so the
 * user can be anywhere in the app while the worker fills the record in. An
 * edit made meanwhile would be overwritten the moment the extraction lands,
 * so the record stays closed for editing until the run finishes. Nothing is
 * persisted: a reload ends the run this tracks.
 */
type AutofillLocks = {
  locked: string[];
  lock: (id: string) => void;
  unlock: (id: string) => void;
};

export const useAutofillLocks = create<AutofillLocks>((set) => ({
  locked: [],
  lock: (id) => set((state) => (state.locked.includes(id) ? state : { locked: [...state.locked, id] })),
  unlock: (id) => set((state) => ({ locked: state.locked.filter((other) => other !== id) })),
}));

/** True while a document is being read into this record. */
export function useIsAutofilling(id: string | null | undefined) {
  return useAutofillLocks((state) => (id ? state.locked.includes(id) : false));
}
