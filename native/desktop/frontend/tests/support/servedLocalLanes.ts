import type { AgentLocalEngineToken } from "../../src/ipc/contract";
import { servedCatalogFor } from "../../src/dev/fixtures/agentCatalog";
import { FIXTURE_DEFAULT_ENGINE } from "../../src/dev/fixtures/localEngineRecord";
import { FIXTURE_SETTINGS_LANES } from "../../src/dev/providerSettingsFixture";

// The keyless lanes of this computer that the scenario host serves, read from
// the catalogue the host serves for the engine its record selects: the host,
// as the service does, leaves out the lane of an engine that is not selected,
// so nothing here decides which lanes an engine has.

export type ServedEngine = AgentLocalEngineToken;

/** The scenario host's default engine setting. */
export const SERVED_ENGINE: ServedEngine = FIXTURE_DEFAULT_ENGINE;

export type ServedLocalLane = {
  id: string;
  /** The models the catalogue recommends for the lane. */
  recommended: string[];
};

/** The local lanes the window shows, in catalogue order. */
export function servedLocalLanes(
  engine: ServedEngine = SERVED_ENGINE,
): ServedLocalLane[] {
  const keyless = new Set(
    FIXTURE_SETTINGS_LANES.filter((seed) => seed.auth_kind === "none").map(
      (seed) => seed.id,
    ),
  );
  return (servedCatalogFor(engine).providers ?? []).flatMap((lane) => {
    const id = `${lane.provider_id}_${lane.transport}`;
    if (!keyless.has(id)) return [];
    return [
      {
        id,
        recommended: [
          ...new Set(Object.values(lane.catalog.recommended ?? {})),
        ],
      },
    ];
  });
}
