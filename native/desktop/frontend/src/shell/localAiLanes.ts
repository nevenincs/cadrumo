import { useCallback, useMemo, useState } from "react";
import type { AgentSession } from "./agentSession";
import { useAgentRead } from "./agentViews";
import { useAgentStatus } from "./agentLive";
import { catalogLanes, type CatalogLane } from "./localModelLanes";
import type { LocalModelHost } from "./localModels";
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
  const available = status?.state === "ready" || status?.state === "starting";
  const [retries, setRetries] = useState(0);
  const request = useMemo(
    () => ({ session, providerSettings, reader, again, retries }),
    [session, providerSettings, reader, again, retries],
  );
  const readLanes = useMemo(() => {
    const { session, providerSettings, reader } = request;
    if (
      !active ||
      !available ||
      !session ||
      !providerSettings ||
      reader === null
    )
      return null;
    return async () => {
      const [catalog, settings] = await Promise.all([
        session.providerCatalog(),
        providerSettings.status(),
      ]);
      const keyless = new Set(
        settings.providers
          .filter((lane) => lane.auth_kind === "none")
          .map((lane) => lane.id),
      );
      return catalogLanes(catalog).filter((lane) => keyless.has(lane.id));
    };
  }, [active, available, request]);
  const read = useAgentRead(readLanes);
  const retry = useCallback(() => setRetries((count) => count + 1), []);
  const host = useMemo((): LocalModelHost | null => {
    if (
      !available ||
      !session?.localModels ||
      !session.addLocalModel ||
      !session.removeLocalModel ||
      !session.resetLocalModels
    )
      return null;
    return {
      read: session.localModels.bind(session),
      add: session.addLocalModel.bind(session),
      remove: session.removeLocalModel.bind(session),
      reset: session.resetLocalModels.bind(session),
    };
  }, [session, available]);
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
