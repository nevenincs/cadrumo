import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useMemo, useRef, useState } from "react";
import { fixtureAgent } from "@/dev/agentFixtureHost";
import { FIXTURE_CATALOG } from "@/dev/fixtures/agentCatalog";
import { setupFixture } from "@/dev/setupFixture";
import { useSetup } from "../../shell/setup";
import { SetupDialog } from "../setup/SetupDialog";
import { roleLanes } from "../../shell/agentModelRoles";
import type { ModelRoleHost } from "../../shell/modelRoles";
import { ModelRolesDialog } from "../agent/ModelRolesDialog";
import { LocalModels } from "./LocalModels";
import { ProviderSettings } from "./ProviderSettings";
import { PROVIDERS } from "./ProviderSettings.stories";
import type { ProviderStatus } from "./types";

// The real provider settings of the made-up lane that runs on this computer,
// opened, with the real model list. The switch turns the lane off and on;
// document configuration is separate; Download opens the
// shared setup review and marks the model as here only after approved setup, and
// Remove takes it off again. Everything is kept in memory and forgotten on
// reload, and nothing is downloaded. Every lane and model is made up.

const LANE = "local_api";

const LOCAL_LANE =
  roleLanes(FIXTURE_CATALOG).find((held) => held.id === LANE) ?? null;

/** The lane on this computer, turned on and ready. */
const LOCAL_PROVIDER: ProviderStatus = {
  ...PROVIDERS.find((provider) => provider.id === LANE)!,
  mode: "key",
  readiness: "ready",
  source: "profile",
};

type Scene = {
  /** A role that already selects a model of the lane. */
  selected?: { role: string; model: string };
  /** Another window changes the roles once they are read, so the next change
   * made here is refused as out of date. */
  staleAfterRead?: boolean;
  /** What a removal answers: null removes the model. */
  removal?: string | null;
};

/** The made-up agent's own model roles, as the settings read and change them. */
function roleHost({ selected, staleAfterRead }: Scene): ModelRoleHost {
  const { session, changeRolesElsewhere } = fixtureAgent({
    say: () => undefined,
    wait: () => Promise.resolve(),
    signedIn: () => true,
    readable: () => true,
    empty: true,
    stream: "steady",
    asks: null,
    refused: () => new Error("refused"),
  });
  const { modelRoles, setModelRole, clearModelRole } = session;
  if (!modelRoles || !setModelRole || !clearModelRole)
    throw new Error("The made-up agent offers no model roles.");
  const seeded = selected
    ? modelRoles.call(session).then((held) => {
        if (held.state !== "readable")
          throw new Error("The made-up roles are unreadable.");
        return setModelRole.call(
          session,
          selected.role,
          LANE,
          selected.model,
          held.revision,
        );
      })
    : Promise.resolve();
  return {
    read: async () => {
      await seeded;
      const held = await modelRoles.call(session);
      if (staleAfterRead) changeRolesElsewhere();
      return held;
    },
    set: setModelRole.bind(session),
    clear: clearModelRole.bind(session),
  };
}

function Settings(scene: Scene) {
  const host = useMemo(() => roleHost(scene), [scene]);
  const root = useRef<HTMLDivElement>(null);
  const [on, setOn] = useState(true);
  // Which models this computer holds, as setup and removal leave them.
  const [held, setHeld] = useState<Record<string, boolean>>({});
  const setupHost = useMemo(
    () =>
      setupFixture({
        shape: "partial",
        latencyMs: 600,
        say: () => undefined,
        readable: () => true,
      }),
    [],
  );
  const setup = useSetup(setupHost, "Demo profile", true);
  const [setupOpen, setSetupOpen] = useState(false);
  const [rolesOpen, setRolesOpen] = useState(false);
  const requested = useRef<string | null>(null);
  const run = setup.snapshot?.setup;
  useEffect(() => {
    if (run?.stage !== "settled" || run.outcome !== "completed") return;
    const model = requested.current;
    if (model) setHeld((now) => ({ ...now, [model]: true }));
  }, [run?.operation_id, run?.stage, run?.outcome]);
  useEffect(() => {
    root.current
      ?.querySelectorAll("details")
      .forEach((node) => (node.open = true));
  }, []);
  const lane = LOCAL_LANE && {
    ...LOCAL_LANE,
    models: LOCAL_LANE.models.map((model) => ({
      ...model,
      installed: held[model.id] ?? model.installed,
    })),
  };
  return (
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
          <LocalModels
            key={`${rolesOpen}`}
            lane={lane}
            host={host}
            locale="en"
            onConfigure={() => setRolesOpen(true)}
            onSetUp={(model) => {
              requested.current = model;
              setSetupOpen(true);
              setup.start(["local_ai"], { download: { lane: LANE, model } });
            }}
            onRemove={(model) => {
              const refusal = scene.removal ?? null;
              if (!refusal) setHeld((now) => ({ ...now, [model]: false }));
              return Promise.resolve(refusal);
            }}
          />
        )}
      />
      {rolesOpen && (
        <ModelRolesDialog
          host={host}
          catalog={FIXTURE_CATALOG}
          locale="en"
          onClose={() => setRolesOpen(false)}
        />
      )}
      <SetupDialog
        open={setupOpen}
        onOpenChange={setSetupOpen}
        control={setup}
        focus="local_ai"
        locale="en"
        onAct={(row) => setup.verify([row.item])}
        onCopyDetails={() => undefined}
      />
    </div>
  );
}

const meta = {
  title: "Shell/Settings/Local models",
  parameters: { surface: "chrome" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

const NONE: Scene = {};
const TEXT_SELECTED: Scene = {
  selected: { role: "text_extraction", model: "synthetic-text:1" },
};
const STALE: Scene = { staleAfterRead: true };
const REMOVAL_FAILS: Scene = { removal: "model_not_removed" };

export const Default: Story = {
  name: "Nothing selected",
  render: () => <Settings {...NONE} />,
};

export const RoleSelected: Story = {
  name: "A role selects a model",
  render: () => <Settings {...TEXT_SELECTED} />,
};

export const Refused: Story = {
  name: "Change refused as out of date",
  render: () => <Settings {...STALE} />,
};

export const RemovalFailed: Story = {
  name: "Removal failed",
  render: () => <Settings {...REMOVAL_FAILS} />,
};
