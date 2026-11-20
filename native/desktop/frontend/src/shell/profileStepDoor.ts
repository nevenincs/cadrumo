import { createContext, useContext } from "react";
import type { LedgerProfileStep } from "./ledger";

// Where a refusal elsewhere sends the person to put their profile right: the
// profile page, opened on the detail the step names. A surface that shows a
// served profile step leads there. The window offers the door only where it
// has a profile page and the person is signed in.

/** Opens the profile page on the step the backend served. */
export type ProfileStepDoor = (step: LedgerProfileStep) => void;

export const ProfileStepContext = createContext<ProfileStepDoor | null>(null);

/** The way to the profile page for a served step, or null where the window
 * offers none. */
export function useProfileStepDoor(): ProfileStepDoor | null {
  return useContext(ProfileStepContext);
}
