import { useEffect } from "react";
import type { Host } from "./host";

const ACTIVITY_INTERVAL_MS = 15_000;

/** Only real input extends person activity; rendering and polling do not. */
export function usePersonActivity(host: Host, signedIn: boolean): void {
  useEffect(() => {
    const noteActivity = host.noteActivity;
    if (!signedIn || !noteActivity) return;
    let lastSent = -Infinity;
    let pending = false;
    const observe = (event: Event) => {
      if (!event.isTrusted || pending) return;
      const now = performance.now();
      if (now - lastSent < ACTIVITY_INTERVAL_MS) return;
      lastSent = now;
      pending = true;
      // The ordinary status observer owns connection/session presentation.
      // A rejected activity report must never become an unhandled rejection.
      void noteActivity()
        .catch(() => undefined)
        .finally(() => {
          pending = false;
        });
    };
    const names = ["keydown", "pointerdown", "wheel", "paste"] as const;
    names.forEach((name) =>
      window.addEventListener(name, observe, { capture: true, passive: true }),
    );
    return () =>
      names.forEach((name) => window.removeEventListener(name, observe, true));
  }, [host, signedIn]);
}
