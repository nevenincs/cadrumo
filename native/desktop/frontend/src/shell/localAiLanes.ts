import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { AgentCatalogAnswer, AgentSession } from "./agentSession";
import { failureCode } from "../errors";
import type { AgentRead } from "./agentViews";
import {
  CATALOG_BUSY_RETRIES,
  CATALOG_BUSY_PAUSE_MS,
  catalogReadBusy,
  catalogReadRetry,
} from "./catalogReadPolicy";
import { useAgentStatus } from "./agentLive";
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
  retry: () => void;
};

/**
 * The keyless lanes of `source` and the person's lists of them, read while
 * `active`. A change of `again` reads the catalog again, as after a setup
 * that may have downloaded a model.
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
    let attempts = 0;
    let timer: number | undefined;
    const current = () => alive && mine === generation.current;
    const put = (read: AgentRead<CatalogLane[]>) => {
      if (current()) setState({ for: request, read });
    };
    const retryBusy = (
      code: string,
      busy: boolean,
      atRead: typeof published.current,
      collect: () => Promise<void>,
    ) => {
      if (!current()) return;
      if (!busy || attempts >= CATALOG_BUSY_RETRIES) {
        put({ kind: "failed", code });
        return;
      }
      const pause = CATALOG_BUSY_PAUSE_MS * 2 ** attempts;
      attempts += 1;
      const resume = () => {
        if (!current() || wake.current !== resume) return;
        void collect();
      };
      wake.current = resume;
      timer = window.setTimeout(resume, pause);
      // A publication during this read is also a recovery signal. Both
      // publications and fallback timers spend the same bounded budget.
      if (atRead !== published.current) resume();
    };
    const collectSettings = async (catalog: AgentCatalogAnswer) => {
      if (!current()) return;
      wake.current = null;
      window.clearTimeout(timer);
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
        // Only an explicit busy refusal permits collecting the native cold
        // status probe under this owner and admitted catalog.
        retryBusy(code, code === "busy", atRead, () =>
          collectSettings(catalog),
        );
      }
    };
    const collect = async () => {
      if (!current()) return;
      wake.current = null;
      window.clearTimeout(timer);
      const atRead = published.current;
      let catalog;
      try {
        // Each busy read the lanes follow is part of the wait they expect;
        // the one they give up on is the failure.
        catalog = await session.providerCatalog(
          catalogReadRetry(
            () => current() && attempts < CATALOG_BUSY_RETRIES,
            () => true,
          ),
        );
      } catch (error) {
        const code = failureCode(error);
        retryBusy(code, catalogReadBusy(code), atRead, collect);
        return;
      }
      // Catalog admission precedes the independent provider-status probe;
      // neither a busy catalog nor a retired read may start that probe.
      if (current()) await collectSettings(catalog);
    };
    put({ kind: "loading" });
    void collect();
    return () => {
      if (work.current === mineWork) work.current = null;
      alive = false;
      window.clearTimeout(timer);
      wake.current = null;
    };
  }, [request, available]);
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
    retry,
  };
}
