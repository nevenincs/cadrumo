import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useState } from "react";
import { setupFixture, type SetupShape } from "../../dev/setupFixture";
import { useSetup } from "../../shell/setup";
import { SetupAdvisory } from "./SetupAdvisory";
import { SetupDialog } from "./SetupDialog";

// The setup dialog and Settings advisory over the scenario host's synthetic setup:
// nothing is downloaded, and a setup the story starts runs by itself, a step
// every `latencyMs`.
const noop = () => undefined;

function Screen({
  shape,
  latencyMs,
  settings,
  focus,
}: {
  shape: SetupShape;
  latencyMs: number;
  settings: boolean;
  focus: string | null;
}) {
  const host = useMemo(
    () =>
      setupFixture({
        shape,
        latencyMs,
        say: noop,
        readable: () => true,
      }),
    [shape, latencyMs],
  );
  const control = useSetup(host, "Demo profile", true);
  const [open, setOpen] = useState(!settings);
  return (
    <>
      {settings && (
        <div className="grid w-settings gap-3 bg-popover p-3.5">
          <SetupAdvisory control={control} onOpen={() => setOpen(true)} />
        </div>
      )}
      <SetupDialog
        open={open}
        onOpenChange={setOpen}
        control={control}
        focus={focus}
        locale="en"
        onAct={(row) => control.verify([row.item])}
        onCopyDetails={noop}
      />
    </>
  );
}

type Args = {
  shape: SetupShape;
  latencyMs: number;
  settings: boolean;
  /** The item the dialog is opened for; the browser has a flow of its own. */
  focus: string | null;
};

const meta = {
  title: "Shell/Setup",
  parameters: { fill: true },
  args: { shape: "fresh", latencyMs: 600, settings: false, focus: null },
  render: (args: Args) => <Screen {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const FirstRun: Story = {};
export const OneNeedsAttention: Story = { args: { shape: "partial" } };
export const Interrupted: Story = { args: { shape: "interrupted" } };
export const Offline: Story = { args: { shape: "offline" } };
export const BelowHardware: Story = { args: { shape: "hardware" } };
export const TooLittleSpace: Story = { args: { shape: "low_space" } };
export const Unavailable: Story = { args: { shape: "unavailable" } };
export const SettingsIncomplete: Story = { args: { settings: true } };
export const BrowserFlow: Story = { args: { focus: "browser" } };
export const BrowserReady: Story = {
  args: { focus: "browser", shape: "partial" },
};
export const SettingsComplete: Story = {
  args: { settings: true, shape: "ready" },
};
export const SettingsGoogleSignedOut: Story = {
  args: { settings: true, shape: "google_signed_out" },
};
