import { FIXTURE_CATALOG } from "../../src/dev/fixtures/agentCatalog";
import { FIXTURE_SETTINGS_LANES } from "../../src/dev/providerSettingsFixture";

// The keyless lanes of this computer that the scenario host serves, written
// from the host's own declarations. A lane named for a local engine is served
// only while that engine is the one the engine setting selects.
const ENGINES = ["llamacpp", "ollama"] as const;

export type ServedEngine = (typeof ENGINES)[number];

/** The scenario host's default engine setting. */
export const SERVED_ENGINE: ServedEngine = "llamacpp";

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
  return (FIXTURE_CATALOG.providers ?? []).flatMap((lane) => {
    const id = `${lane.provider_id}_${lane.transport}`;
    const held = (ENGINES as readonly string[]).includes(lane.provider_id)
      ? lane.provider_id !== engine
      : false;
    if (!keyless.has(id) || held) return [];
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
