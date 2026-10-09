import { useEffect, useState } from "react";
import type { DesktopEnvironment } from "@/ipc/contract";
import { HostUnavailable, type Host } from "./host";

type Environment =
  | { state: "loading" }
  | { state: "ready"; value: DesktopEnvironment }
  /** There is no desktop host to ask: the page runs in a plain browser. */
  | { state: "unavailable" }
  /** The host was asked and could not answer. */
  | { state: "failed" };

export function useDesktopEnvironment(host: Host): Environment {
  const [environment, setEnvironment] = useState<Environment>({
    state: "loading",
  });
  useEffect(() => {
    let current = true;
    host
      .environment()
      .then((value) => current && setEnvironment({ state: "ready", value }))
      .catch(
        (error: unknown) =>
          current &&
          setEnvironment({
            state: error instanceof HostUnavailable ? "unavailable" : "failed",
          }),
      );
    return () => {
      current = false;
    };
  }, [host]);

  return environment;
}
