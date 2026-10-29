import { useEffect, useMemo, useRef, type ReactNode } from "react";
import type { SetupItemId, SetupModelDownload } from "../ipc/contract";
import type { LocalAiSource } from "../shell/localAiLanes";
import type { LocalModelHost } from "../shell/localModels";
import {
  ProvisioningContext,
  useProvisioningStore,
} from "../shell/provisioning";
import { useSetup } from "../shell/setup";
import { fixtureAgent } from "./agentFixtureHost";
import type { FixtureModelPresence } from "./fixtures/agentCatalog";
import { providerSettingsFixture } from "./providerSettingsFixture";
import { setupFixture, type SetupShape } from "./setupFixture";

// A story's provisioning store over the scenario host's synthetic setup, the
// same store the window keeps: nothing is downloaded, and a setup a story
// starts runs by itself, a step every `latencyMs`. A story names the setups
// it starts once the first status is read, and whether their plans are
// approved, so a state such as two setups running side by side is reached
// the way a person reaches it.

/** One setup a story starts: one item, and the model it downloads. */
export type StagedStart = {
  item: SetupItemId;
  download?: SetupModelDownload;
  /** Approves the plan once it is shown. */
  approve?: boolean;
};

export function ProvisioningStage({
  shape,
  latencyMs,
  starts = [],
  openPanel = false,
  models,
  children,
}: {
  shape: SetupShape;
  latencyMs: number;
  starts?: readonly StagedStart[];
  /** Opens the provisioning panel at once. */
  openPanel?: boolean;
  /** Where a model the setup downloads is marked held, for the agent of
   * `stageLocalAi` to report. */
  models?: FixtureModelPresence;
  children: ReactNode;
}) {
  const host = useMemo(
    () =>
      setupFixture({
        shape,
        latencyMs,
        say: () => undefined,
        readable: () => true,
        ...(models ? { models } : {}),
      }),
    [shape, latencyMs, models],
  );
  const control = useSetup(host, "Demo profile");
  const store = useProvisioningStore(control, "Demo profile");
  const { snapshot, start, answer } = control;
  const read = snapshot !== null && snapshot.rows.length > 0;
  const { open } = store;
  useEffect(() => {
    if (openPanel) open(null);
  }, [openPanel, open]);
  const started = useRef(false);
  useEffect(() => {
    if (!read || started.current) return;
    started.current = true;
    for (const wanted of starts)
      start(wanted.item, wanted.download ? { download: wanted.download } : {});
  }, [read, starts, start]);
  const approved = useRef(new Set<string>());
  useEffect(() => {
    for (const run of snapshot?.runs ?? []) {
      const wanted = starts.find((held) => held.item === run.item);
      if (
        !wanted?.approve ||
        run.stage !== "review" ||
        approved.current.has(run.operation_id)
      )
        continue;
      approved.current.add(run.operation_id);
      answer(run.item, "apply");
    }
  }, [snapshot, starts, answer]);
  return (
    <ProvisioningContext.Provider value={store}>
      {children}
    </ProvisioningContext.Provider>
  );
}

/** The made-up agent's own local model lists, as the settings read and
 * change them; `added` is on the list already. */
export function stageListHost(lane: string, added?: string): LocalModelHost {
  const { session } = fixtureAgent({
    say: () => undefined,
    wait: () => Promise.resolve(),
    signedIn: () => true,
    readable: () => true,
    empty: true,
    stream: "steady",
    asks: null,
    refused: () => new Error("refused"),
  });
  const { localModels, addLocalModel, removeLocalModel, resetLocalModels } =
    session;
  if (!localModels || !addLocalModel || !removeLocalModel || !resetLocalModels)
    throw new Error("The made-up agent offers no model list.");
  const seeded = added
    ? localModels
        .call(session)
        .then((held) => addLocalModel.call(session, lane, added, held.revision))
    : Promise.resolve();
  return {
    read: async () => {
      await seeded;
      return localModels.call(session);
    },
    add: addLocalModel.bind(session),
    remove: removeLocalModel.bind(session),
    reset: resetLocalModels.bind(session),
  };
}

/** The made-up profile's provider settings and agent, where the panel reads
 * the local AI's model lists from; its catalog reports `models` as held. */
export function stageLocalAi(models?: FixtureModelPresence): LocalAiSource {
  const { settings } = providerSettingsFixture({
    say: () => undefined,
    wait: () => Promise.resolve(),
    readable: () => true,
  });
  const { session } = fixtureAgent({
    say: () => undefined,
    wait: () => Promise.resolve(),
    signedIn: () => true,
    readable: () => true,
    empty: true,
    stream: "steady",
    asks: null,
    refused: () => new Error("refused"),
    ...(models ? { models } : {}),
  });
  return { session, providerSettings: settings, reader: "Demo profile" };
}
