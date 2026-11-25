import { useEffect, useRef } from "react";
import { saveState, type Layout, type Prefs } from "./layout";

/** Debounces workspace changes and flushes the last state on page exit. */
export function usePersistedLayout(
  prefs: Prefs,
  layout: Layout,
  delayMs: number,
) {
  const unsaved = useRef({ prefs, layout });
  useEffect(() => {
    unsaved.current = { prefs, layout };
    const timer = window.setTimeout(() => saveState(prefs, layout), delayMs);
    return () => window.clearTimeout(timer);
  }, [prefs, layout, delayMs]);
  useEffect(() => {
    // Leaving before the pause has passed still keeps the last change.
    const flush = () =>
      saveState(unsaved.current.prefs, unsaved.current.layout);
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, []);
}
