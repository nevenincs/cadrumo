import { useMemo } from "react";
import type { AgentSession } from "./agentSession";
import { useAgentRead } from "./agentViews";
import { catalogLanes, type CatalogLane } from "./localModelLanes";
import type { LocalModelHost } from "./localModels";
import { useProviderSettings, type ProviderSettings } from "./providerSettings";

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
  const reader = source?.reader ?? null;
  const settings = useProviderSettings(
    source?.providerSettings,
    reader,
    active && source !== null,
    0,
  );
  const readCatalog = useMemo(
    () =>
      active && session && reader !== null
        ? () => session.providerCatalog()
        : null,
    [active, session, reader],
  );
  const catalog = useAgentRead(readCatalog, again);
  const lanes = useMemo(() => {
    if (catalog.kind !== "ready" || settings.read.kind !== "ready") return [];
    const keyless = new Set(
      settings.read.value.providers
        .filter((lane) => lane.authKind === "none")
        .map((lane) => lane.id),
    );
    return catalogLanes(catalog.value).filter((lane) => keyless.has(lane.id));
  }, [catalog, settings.read]);
  const host = useMemo((): LocalModelHost | null => {
    if (
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
  }, [session]);
  return { lanes, host };
}
