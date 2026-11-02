import { useEffect } from "react";
import type { Host } from "../host";
import { notifyInternalFailure } from "../internalFailures";
import type { useNavigator } from "./useNavigator";

/** Connects native close requests to the same guards used by navigation.
 * A subscription arriving after teardown is released immediately.
 */
export function useWindowCloseGuard(
  host: Host,
  guardNavigation: ReturnType<typeof useNavigator>["guard"],
) {
  // A close the system raised (the window's own close, Alt+F4) asks the
  // page through the host, which holds the window until the page answers.
  useEffect(() => {
    const windowPort = host.window;
    if (!windowPort?.guardClose) return;
    let release: (() => void) | null = null;
    let current = true;
    void windowPort
      .guardClose(() =>
        guardNavigation(
          { kind: "close" },
          () =>
            void windowPort.action("close_now").catch(notifyInternalFailure),
          () =>
            void windowPort.action("keep_open").catch(notifyInternalFailure),
        ),
      )
      .then((stop) => {
        if (current) release = stop;
        else stop();
      })
      .catch(() => undefined);
    return () => {
      current = false;
      release?.();
    };
  }, [host, guardNavigation]);
}
