import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useRef, useState } from "react";
import { fixtureAgent } from "@/dev/agentFixtureHost";
import { FIXTURE_CATALOG } from "@/dev/fixtures/agentCatalog";
import { ProvisioningStage } from "@/dev/ProvisioningStage";
import { catalogLanes } from "../../shell/localModelLanes";
import type { LocalModelHost } from "../../shell/localModels";
import { LocalModels } from "./LocalModels";
import { ProviderSettings } from "./ProviderSettings";
import { PROVIDERS } from "./ProviderSettings.stories";
import type { ProviderStatus } from "./types";

// The real provider settings of the made-up lane that runs on this computer,
// opened, with the real model list: the agent's recommended models and the
// ones added by name. The switch turns the lane off and on; Download starts
// the local AI's setup of that model through the window's provisioning
// store, whose progress the model shows, and Remove takes it off again.
// Everything is kept in memory and forgotten on reload, and nothing is
// downloaded. Every lane and model is made up.

const LANE = "local_api";

const LOCAL_LANE =
  catalogLanes(FIXTURE_CATALOG).find((held) => held.id === LANE) ?? null;

/** The lane on this computer, turned on and ready. */
const LOCAL_PROVIDER: ProviderStatus = {
  ...PROVIDERS.find((provider) => provider.id === LANE)!,
  mode: "key",
  readiness: "ready",
  source: "profile",
};

type Scene = {
  /** A model already added to the list by name. */
  added?: string;
  /** Another window changes the list once it is read, so the next change
   * made here is refused as out of date. */
  staleAfterRead?: boolean;
};

/** The made-up agent's own model list, as the settings read and change it. */
function listHost({ added, staleAfterRead }: Scene): LocalModelHost {
  const { session, changeListElsewhere } = fixtureAgent({
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
        .then((held) => addLocalModel.call(session, LANE, added, held.revision))
    : Promise.resolve();
  return {
    read: async () => {
      await seeded;
      const held = await localModels.call(session);
      if (staleAfterRead) changeListElsewhere();
      return held;
    },
    add: addLocalModel.bind(session),
    remove: removeLocalModel.bind(session),
    reset: resetLocalModels.bind(session),
  };
}

function Settings(scene: Scene) {
  const host = useMemo(() => listHost(scene), [scene]);
  const root = useRef<HTMLDivElement>(null);
  const [on, setOn] = useState(true);
  useEffect(() => {
    root.current
      ?.querySelectorAll("details")
      .forEach((node) => (node.open = true));
  }, []);
  return (
    <ProvisioningStage shape="partial" latencyMs={600}>
      <div ref={root} className="w-settings max-w-full">
        <ProviderSettings
          providers={[
            on
              ? LOCAL_PROVIDER
              : { ...LOCAL_PROVIDER, mode: "disabled", readiness: "disabled" },
          ]}
          onSave={() => undefined}
          onTurnOff={() => setOn(false)}
          onTurnOn={() => setOn(true)}
          onReset={() => undefined}
          onRefresh={() => undefined}
          localModels={() => (
            <LocalModels lane={LOCAL_LANE} host={host} locale="en" />
          )}
        />
      </div>
    </ProvisioningStage>
  );
}

const meta = {
  title: "Shell/Settings/Local models",
  parameters: { surface: "chrome" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

const RECOMMENDED: Scene = {};
const ADDED: Scene = { added: "synthetic-named:test" };
const STALE: Scene = { staleAfterRead: true };

export const Default: Story = {
  name: "The recommended models",
  render: () => <Settings {...RECOMMENDED} />,
};

export const Added: Story = {
  name: "A model added by name",
  render: () => <Settings {...ADDED} />,
};

export const Refused: Story = {
  name: "Change refused as out of date",
  render: () => <Settings {...STALE} />,
};
