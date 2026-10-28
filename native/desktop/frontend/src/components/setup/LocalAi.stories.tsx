import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo } from "react";
import {
  ProvisioningStage,
  stageListHost,
  type StagedStart,
} from "../../dev/ProvisioningStage";
import { FIXTURE_CATALOG } from "../../dev/fixtures/agentCatalog";
import type { SetupShape } from "../../dev/setupFixture";
import { catalogLanes } from "../../shell/localModelLanes";
import { LocalAi } from "./LocalAi";

// The local AI's one component, as the provisioning panel and the agent's
// settings for the lane on this computer both render it: the program that
// runs the models, with its own status and controls, and beneath it the
// person's model list, each model with its own download, progress and
// removal. Over the scenario host's synthetic setup and the made-up agent's
// lists; nothing is downloaded. Every lane and model is made up.

const LOCAL_LANE =
  catalogLanes(FIXTURE_CATALOG).find(
    (lane) => lane.recommended.length > 0 && lane.provider === "local",
  ) ?? null;
const MODEL_DOWNLOAD = LOCAL_LANE
  ? { lane: LOCAL_LANE.id, model: LOCAL_LANE.recommended[0] ?? "" }
  : undefined;

type Args = {
  shape: SetupShape;
  latencyMs: number;
  starts: StagedStart[];
  /** A model already on the list, added by name. */
  added?: string;
};

function Screen({ shape, latencyMs, starts, added }: Args) {
  const host = useMemo(
    () => (LOCAL_LANE ? stageListHost(LOCAL_LANE.id, added) : null),
    [added],
  );
  return (
    <ProvisioningStage shape={shape} latencyMs={latencyMs} starts={starts}>
      <div className="w-dialog max-w-full rounded-lg bg-accent p-3">
        <LocalAi
          lanes={LOCAL_LANE ? [LOCAL_LANE] : []}
          host={host}
          locale="en"
        />
      </div>
    </ProvisioningStage>
  );
}

const meta = {
  title: "Shell/Setup/Local AI",
  parameters: { surface: "chrome" },
  args: { shape: "fresh", latencyMs: 900, starts: [] },
  render: (args: Args) => <Screen {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

/** Neither the program nor any model is on this computer. */
export const Absent: Story = {};

/** A model's download, planned with the missing program first, awaiting an
 * answer in the program's row. */
export const Review: Story = {
  args: { starts: [{ item: "local_ai", download: MODEL_DOWNLOAD }] },
};

/** The program, then the model, each with its own progress. */
export const RunningWithParts: Story = {
  args: {
    starts: [{ item: "local_ai", download: MODEL_DOWNLOAD, approve: true }],
  },
};

/** The last setup's download was damaged: the program offers to try again. */
export const Failed: Story = { args: { shape: "partial" } };

/** The program is ready, with a model added by name. */
export const Ready: Story = {
  args: { shape: "ready", added: "synthetic-named:test" },
};

/** This computer cannot run the local AI; the list still says what each
 * model is. */
export const BelowHardware: Story = { args: { shape: "hardware" } };
