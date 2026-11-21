import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ServedCatalogAnswer } from "./agentCatalogContract";
import type { AgentServiceStatus, AgentSession } from "./agentSession";
import { failureCode } from "../errors";
import type { AgentRead } from "./agentViews";
import { useAgentStatus } from "./agentLive";
import { modelListState, useWindowReturn } from "./modelListState";
import { catalogLanes, type CatalogLane } from "./localModelLanes";
import { localModelHostOf, type LocalModelHost } from "./localModels";
import type { ProviderSettings } from "./providerSettings";

// The local AI's model lists outside the agent column: the lanes that need
// no key, as the profile's provider settings name them, with the models
// cadrumo-agent's catalog lists for each, and the person's lists to change.
// Read only while a surface shows them.

/** What the window offers for reading the local lanes. */
export type LocalAiSource = {
  session: AgentSession;
  providerSettings: ProviderSettings;
  /** The signed-in profile the lanes belong to. */
  reader: string | null;
};

export type LocalAiLanes = {
  lanes: CatalogLane[];
  host: LocalModelHost | null;
  status: "loading" | "failed" | "ready";
  /** The refusal the lanes' read answered, while `status` is failed. */
  failure: string | null;
  /** The agent service's status while it does not serve the lanes, which
   * is said in their place; null while it serves them or is not known. */
  service: AgentServiceStatus | null;
  retry: () => void;
};

/**
 * The keyless lanes of `source` and the person's lists of them, read while
 * `active`. A change of `again` reads the catalog again, as after a setup
 * that may have downloaded a model. A read that answers where setup stands
 * is read again on the next status the service publishes, or when the person
 * comes back to the window; nothing asks again on a timer.
 */
export function useLocalAiLanes(
  source: LocalAiSource | null,
  active: boolean,
  again: number,
): LocalAiLanes {
  const session = source?.session ?? null;
  const providerSettings = source?.providerSettings ?? null;
  const reader = source?.reader ?? null;
  const status = useAgentStatus(session ?? undefined, reader, active);
  // The service answers reads only once it runs; while it starts the host has
  // no connection to it and refuses them, so nothing is asked and the lanes
  // stay loading.
  const available = status?.state === "ready";
  const starting = status?.state === "starting";
  const [retries, setRetries] = useState(0);
  // The agent serves other lanes once it runs under a newly chosen engine:
  // an engine stored through the host reads the lanes again, as does the
  // agent being ready again after it.
  const [engineChanges, setEngineChanges] = useState(0);
  const request = useMemo(
    () => ({
      session,
      providerSettings,
      reader,
      active,
      available,
      again,
      retries,
      engineChanges,
    }),
    [
      session,
      providerSettings,
      reader,
      active,
      available,
      again,
      retries,
      engineChanges,
    ],
  );
  const generation = useRef(0);
  // The work of the commit now reading, so the window's learning that the
  // session ended can be told to the reads it has in flight.
  const work = useRef<{ ended: boolean } | null>(null);
  useLayoutEffect(() => {
    if (reader === null && work.current) work.current.ended = true;
  }, [reader]);
  const wake = useRef<(() => void) | null>(null);
  const published = useRef(status);
  useLayoutEffect(() => {
    published.current = status;
  }, [status]);
  // Retire on commit, before any obsolete promise can issue its dependent
  // settings read or publish into a new profile/host/visibility generation.
  useLayoutEffect(
    () => () => {
      generation.current += 1;
      wake.current = null;
    },
    [request, available],
  );
  const [state, setState] = useState<{
    for: typeof request;
    read: AgentRead<CatalogLane[]>;
  } | null>(null);
  useEffect(() => {
    const { session, providerSettings, reader, active } = request;
    if (
      !active ||
      !available ||
      !session ||
      !providerSettings ||
      reader === null
    )
      return;
    const mine = generation.current;
    const mineWork = { ended: false };
    work.current = mineWork;
    let alive = true;
    const current = () => alive && mine === generation.current;
    const put = (read: AgentRead<CatalogLane[]>) => {
      if (current()) setState({ for: request, read });
    };
    // A state is said and waited on: the next publication or return to the
    // window resumes the read. A fault is said with its retry.
    const refused = (
      code: string,
      atRead: typeof published.current,
      resume: () => Promise<void>,
    ) => {
      if (!current()) return;
      put({ kind: "failed", code });
      if (modelListState(code) === null) return;
      const wakeUp = () => {
        if (!current() || wake.current !== wakeUp) return;
        wake.current = null;
        void resume();
      };
      wake.current = wakeUp;
      // A status published while the read was out is already its cue.
      if (atRead !== published.current) wakeUp();
    };
    const collectSettings = async (catalog: ServedCatalogAnswer) => {
      if (!current()) return;
      wake.current = null;
      const atRead = published.current;
      try {
        const settings = await providerSettings.status({
          sessionEnded: () => mineWork.ended,
        });
        const keyless = new Set(
          settings.providers
            .filter((lane) => lane.auth_kind === "none")
            .map((lane) => lane.id),
        );
        put({
          kind: "ready",
          value: catalogLanes(catalog).filter((lane) => keyless.has(lane.id)),
        });
      } catch (error) {
        const code = failureCode(error);
        // The provider status answers busy while the host has not admitted
        // the service yet: that is the agent starting.
        refused(code === "busy" ? "agent_service_busy" : code, atRead, () =>
          collectSettings(catalog),
        );
      }
    };
    const collect = async () => {
      if (!current()) return;
      wake.current = null;
      const atRead = published.current;
      let catalog;
      try {
        catalog = await session.providerCatalog();
      } catch (error) {
        refused(failureCode(error), atRead, collect);
        return;
      }
      // Catalog admission precedes the independent provider-status probe;
      // neither a refused catalog nor a retired read may start that probe.
      if (current()) await collectSettings(catalog);
    };
    put({ kind: "loading" });
    void collect();
    return () => {
      if (work.current === mineWork) work.current = null;
      alive = false;
      wake.current = null;
    };
  }, [request, available]);
  // A publication after a read that answered a state is its cue, and so is
  // the person coming back to the window.
  useEffect(() => {
    wake.current?.();
  }, [status]);
  const read: AgentRead<CatalogLane[]> =
    active && available && reader !== null && state?.for === request
      ? state.read
      : {
          kind:
            active && (available || starting) && reader !== null
              ? "loading"
              : "unavailable",
        };
  const waiting = read.kind === "failed" && modelListState(read.code) !== null;
  useWindowReturn(waiting ? () => wake.current?.() : null);
  const retry = useCallback(() => setRetries((count) => count + 1), []);
  const host = useMemo(
    (): LocalModelHost | null =>
      available
        ? localModelHostOf(session ?? undefined, (change) => {
            if (change === "engine") setEngineChanges((count) => count + 1);
          })
        : null,
    [session, available],
  );
  return {
    lanes: read.kind === "ready" ? read.value : [],
    host,
    status:
      read.kind === "ready"
        ? "ready"
        : read.kind === "loading"
          ? "loading"
          : "failed",
    failure: read.kind === "failed" ? read.code : null,
    service:
      active && reader !== null && status !== null && status.state !== "ready"
        ? status
        : null,
    retry,
  };
}
