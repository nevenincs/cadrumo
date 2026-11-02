import { useCallback, useEffect, useRef, useState } from "react";
import type { WindowPresentation } from "../ipc/contract";
import type { Host } from "./host";
import type { DockPane } from "./docking";

/** Native observation is shared with the titlebar's single subscription. */
export function useFullscreen(host: Host, onFailure: () => void) {
  const [fullscreen, setFullscreen] = useState(false);
  const [pane, setPane] = useState<DockPane | null>(null);
  const requested = useRef<DockPane | null>(null);
  const pending = useRef(false);
  const observed = useRef(false);
  const failed = useRef(onFailure);
  failed.current = onFailure;
  const observe = useCallback(
    (state: Pick<WindowPresentation, "fullscreen">) => {
      setFullscreen(state.fullscreen);
      setPane(state.fullscreen ? requested.current : null);
      if (!state.fullscreen && observed.current) requested.current = null;
      observed.current = state.fullscreen;
    },
    [],
  );
  useEffect(() => {
    if (host.window) return;
    const changed = () =>
      observe({ fullscreen: document.fullscreenElement !== null });
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, [host.window, observe]);
  // Navigation to another pane returns the whole workspace while keeping
  // the native window fullscreen. The prior split remains untouched.
  const reveal = useCallback((target: DockPane | null) => {
    if (requested.current && requested.current !== target) {
      requested.current = null;
      setPane(null);
    }
  }, []);
  const toggle = useCallback(
    (target: DockPane | null = null) => {
      if (pending.current) return;
      pending.current = true;
      const previous = requested.current;
      if (!fullscreen) requested.current = target;
      const action = host.window
        ? host.window.action(
            fullscreen ? "leave_fullscreen" : "toggle_fullscreen",
          )
        : fullscreen
          ? document.exitFullscreen()
          : document.documentElement.requestFullscreen();
      void action
        .catch(() => {
          requested.current = previous;
          failed.current();
        })
        .finally(() => {
          pending.current = false;
        });
    },
    [host.window, fullscreen],
  );
  return { fullscreen, pane, observe, toggle, reveal };
}
