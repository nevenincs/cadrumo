import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import {
  aeatSyncRunFixture,
  type AeatSyncRunMode,
} from "@/dev/aeatSyncRunFixture";
import { withPendingWords } from "@/dev/aeatSyncRunWords";
import type { AeatSyncRunPort } from "../../shell/aeatSyncRun";
import { StringsContext } from "../../shell/strings";
import { AeatSyncProgress } from "./AeatSyncProgress";

// The update from AEAT as it goes, over the scenario port's demo run: under
// way, partly failed, an outcome that could not be confirmed, nothing new,
// stopping, stopped, the AEAT session timing out, and all done. Stop, a
// retry and the sign-in resume move the demo along so each can be followed.

const noop = () => undefined;

function Progress({
  mode,
  language,
}: {
  mode: AeatSyncRunMode;
  language: string;
}) {
  const port = useRef<AeatSyncRunPort | null>(null);
  port.current ??= aeatSyncRunFixture(mode, noop);
  return (
    <StringsContext value={withPendingWords(language)}>
      <div className="mx-auto w-full max-w-3xl p-4">
        <AeatSyncProgress port={port.current} reader="synthetic" />
      </div>
    </StringsContext>
  );
}

const meta: Meta<typeof Progress> = {
  title: "AEAT data/Bringing",
  component: Progress,
  render: (args, { globals }) => (
    <Progress
      key={args.mode}
      {...args}
      language={String(globals.locale ?? "en")}
    />
  ),
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Progress>;

export const Running: Story = { args: { mode: "running" } };
export const PartialFailure: Story = { args: { mode: "partial_failure" } };
export const UnknownOutcome: Story = { args: { mode: "unknown" } };
export const NothingFound: Story = { args: { mode: "nothing_found" } };
export const Stopping: Story = { args: { mode: "stopping" } };
export const Stopped: Story = { args: { mode: "stopped" } };
export const SessionEndedPaused: Story = { args: { mode: "paused" } };
export const AllDone: Story = { args: { mode: "done" } };
