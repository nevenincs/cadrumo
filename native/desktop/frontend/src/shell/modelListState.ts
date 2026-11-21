import { useEffect, useLayoutEffect, useRef } from "react";
import type { Translate } from "./strings";

// A read that lists models can answer where the person's setup stands rather
// than that something failed: the agent still starting, the agent's session
// reconnecting, nobody signed in to it, or its catalogue not there yet. Each
// view that lists models shows such an answer as that state, with the step
// that moves it on, and reads again on the cue that follows it (a published
// status, the window coming back, or the person's own action), never on a
// timer. Any other refusal is a fault, shown as one with its retry.

/** Where the person's setup stands, as a model list read answers it. */
export type ModelListState =
  "starting" | "reconnecting" | "signed_out" | "catalog_unavailable";

/** The state a refusal reports, or null for a refusal that is a fault. */
export function modelListState(code: string): ModelListState | null {
  switch (code) {
    case "agent_service_busy":
    case "agent_service_not_ready":
      return "starting";
    case "agent_reconnecting":
      return "reconnecting";
    case "agent_signed_out":
      return "signed_out";
    case "agent_catalog_unavailable":
    case "agent_local_models_catalog_unavailable":
      return "catalog_unavailable";
    default:
      return null;
  }
}

/** A state in words. */
export function modelListStateWords(t: Translate, state: ModelListState) {
  switch (state) {
    case "starting":
      return t("desktop.agent.service_starting");
    case "reconnecting":
      return t("desktop.account.reconnecting");
    case "signed_out":
      return t("desktop.agent.service_signed_out");
    case "catalog_unavailable":
      return t("desktop.agent.catalog_unavailable");
  }
}

/** Whether a state moves on by the person asking again. The others move on
 * by themselves, and the view reads again on the cue that says so. */
export const askedAgain = (state: ModelListState) =>
  state === "catalog_unavailable";

/**
 * Calls `onReturn` each time the person comes back to the window (it gains
 * focus, or is shown again), while `onReturn` is given. The views that wait
 * on a setup state read again then, as the state may have moved on while the
 * person was elsewhere.
 */
export function useWindowReturn(onReturn: (() => void) | null) {
  const latest = useRef(onReturn);
  useLayoutEffect(() => {
    latest.current = onReturn;
  }, [onReturn]);
  const listening = onReturn !== null;
  useEffect(() => {
    if (!listening) return;
    const back = () => {
      if (document.visibilityState === "visible") latest.current?.();
    };
    window.addEventListener("focus", back);
    document.addEventListener("visibilitychange", back);
    return () => {
      window.removeEventListener("focus", back);
      document.removeEventListener("visibilitychange", back);
    };
  }, [listening]);
}
