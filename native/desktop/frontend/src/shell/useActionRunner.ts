import { useCallback, useRef } from "react";
import type { Action } from "./actions";

/** Runs and looks up the registry's actions by id. What runs is read when it
 * runs, so a handler kept from an earlier render runs the current action. */
export function useActionRunner(actions: Action[]) {
  const actionsRef = useRef(actions);
  actionsRef.current = actions;
  const byId = (id: string) => actions.find((action) => action.id === id);
  const runAction = useCallback(
    (id: string) =>
      actionsRef.current.find((action) => action.id === id)?.run(),
    [],
  );
  // The profile page is large: what it is given stays the same object from
  // one render of the window to the next, so it draws only when it changes.
  const profileAccountActions = useCallback(
    () =>
      ["account.switchProfile", "account.manageProfiles", "account.signOut"]
        .map((id) => actionsRef.current.find((action) => action.id === id))
        .filter((action) => action !== undefined),
    [],
  );
  return { actionsRef, byId, runAction, profileAccountActions };
}
