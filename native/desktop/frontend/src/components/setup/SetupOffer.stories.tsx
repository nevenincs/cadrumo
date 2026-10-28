import type { Meta, StoryObj } from "@storybook/react-vite";
import { ProvisioningStage } from "../../dev/ProvisioningStage";
import type { SetupShape } from "../../dev/setupFixture";
import { ProvisioningPanel } from "./ProvisioningPanel";
import { SetupOffer } from "./SetupOffer";

// What a feature that could not run offers beside its refusal, over the
// scenario host's synthetic setup: the component by name and the way into
// the provisioning panel on it. Where setup cannot change what is missing,
// the component's name and its row's sentence say why, and nothing is
// offered.

function Screen({ shape, action }: { shape: SetupShape; action: string }) {
  return (
    <ProvisioningStage shape={shape} latencyMs={0}>
      <div className="grid w-settings gap-3 bg-popover p-3.5">
        <SetupOffer action={action} />
      </div>
      <ProvisioningPanel locale="en" onCopyDetails={() => undefined} />
    </ProvisioningStage>
  );
}

type Args = { shape: SetupShape; action: string };

const meta = {
  title: "Shell/Setup offer",
  args: { shape: "ready", action: "operator.provision.local_ai" },
  render: (args: Args) => <Screen {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

/** Setup is complete, so the panel does not open by itself: the offer is
 * the way in. */
export const LocalAiReady: Story = {};
export const LocalAiDamaged: Story = { args: { shape: "partial" } };
export const BrowserNotSetUp: Story = {
  args: { shape: "fresh", action: "operator.provision.browser" },
};
/** The computer is below what the local AI needs: it says so, and nothing
 * is offered. */
export const BelowHardware: Story = { args: { shape: "hardware" } };
