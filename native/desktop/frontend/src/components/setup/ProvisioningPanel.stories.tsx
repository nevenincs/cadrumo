import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import {
  ProvisioningStage,
  stageLocalAi,
  type StagedStart,
} from "../../dev/ProvisioningStage";
import {
  FIXTURE_CATALOG,
  fixtureModelPresence,
} from "../../dev/fixtures/agentCatalog";
import type { SetupShape } from "../../dev/setupFixture";
import { catalogLanes } from "../../shell/localModelLanes";
import { ProvisioningPanel } from "./ProvisioningPanel";

// The provisioning panel over the scenario host's synthetic setup: one row
// per element the made-up engine reports, each with its own status, size,
// action, plan review, progress and cancel. Nothing is downloaded; a setup a
// story starts runs by itself, a step every `latencyMs`, and several run at
// once. Every lane and model is made up.

/** The made-up lane on this computer and the first model it recommends. */
const LOCAL_LANE = catalogLanes(FIXTURE_CATALOG).find(
  (lane) => lane.recommended.length > 0 && lane.provider === "local",
);
const MODEL_DOWNLOAD = LOCAL_LANE
  ? { lane: LOCAL_LANE.id, model: LOCAL_LANE.recommended[0] ?? "" }
  : undefined;

type Args = {
  shape: SetupShape;
  latencyMs: number;
  starts: StagedStart[];
};

function Screen({ shape, latencyMs, starts }: Args) {
  // One made-up computer: a model the setup downloads is one the agent's
  // catalog then reports held.
  const models = useMemo(() => fixtureModelPresence(), []);
  const localAi = useMemo(() => stageLocalAi(models), [models]);
  return (
    <ProvisioningStage
      shape={shape}
      latencyMs={latencyMs}
      starts={starts}
      models={models}
      openPanel
    >
      <ProvisioningPanel
        locale="en"
        onCopyDetails={() => undefined}
        localAi={localAi}
      />
    </ProvisioningStage>
  );
}

const meta = {
  title: "Shell/Setup/Provisioning panel",
  parameters: { fill: true },
  args: { shape: "fresh", latencyMs: 900, starts: [] },
  render: (args: Args) => <Screen {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

/** Nothing set up yet: each element offers its own setup. */
export const Absent: Story = {};

/** The browser's plan, awaiting an answer inside its own row. */
export const Review: Story = {
  args: { starts: [{ item: "browser" }] },
};

/** The local AI installs its program, then the model asked for, each part
 * with its own progress. */
export const RunningWithParts: Story = {
  args: {
    starts: [{ item: "local_ai", download: MODEL_DOWNLOAD, approve: true }],
  },
};

/** The browser and the local AI set up at the same time. */
export const ConcurrentRuns: Story = {
  args: {
    starts: [
      { item: "browser", approve: true },
      { item: "local_ai", download: MODEL_DOWNLOAD, approve: true },
    ],
  },
};

/** A download that failed offers to try again. */
export const Failed: Story = { args: { shape: "partial" } };

/** Everything is set up. */
export const Ready: Story = { args: { shape: "ready" } };

/** Offline: each element that needs the network says so and offers a
 * check. */
export const Offline: Story = { args: { shape: "offline" } };

/** This computer cannot run the local AI; the rest is set up. */
export const BelowHardware: Story = { args: { shape: "hardware" } };

/** Too little free space for the plan: approving is not offered. */
export const TooLittleSpace: Story = {
  args: { shape: "low_space", starts: [{ item: "browser" }] },
};

/** The status cannot be read. */
export const Unavailable: Story = { args: { shape: "unavailable" } };
