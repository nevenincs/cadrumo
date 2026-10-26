import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useState } from "react";
import type { SetupRow } from "../../ipc/contract";
import { setupFixture, type SetupShape } from "../../dev/setupFixture";
import {
  LOCAL_AI_SETUP_ACTION,
  ProvisioningRecoveryContext,
  type ProvisioningRecovery,
} from "../../shell/provisioningRecovery";
import { setupTargetOf, useSetup } from "../../shell/setup";
import { SetupOffer } from "./SetupOffer";
import { SetupPrompt } from "./SetupPrompt";

// What a feature that could not run offers beside its refusal, over the
// scenario host's synthetic setup: the component by name and the way into
// the window's one setup prompt. Where setup cannot change what is missing,
// the component's name and its row's sentence say why, and nothing is
// offered.
const noop = () => undefined;

function Screen({ shape, action }: { shape: SetupShape; action: string }) {
  const host = useMemo(
    () =>
      setupFixture({
        shape,
        latencyMs: 0,
        say: noop,
        readable: () => true,
      }),
    [shape],
  );
  const control = useSetup(host, "Demo profile", true);
  const [prompt, setPrompt] = useState<SetupRow | null>(null);
  const rows = control.snapshot?.rows;
  const recovery = useMemo<ProvisioningRecovery>(
    () => ({
      targetOf: (wanted) => setupTargetOf(wanted, rows ?? []),
      offer: (wanted) => {
        const target = setupTargetOf(wanted, rows ?? []);
        if (target === null || target === "general") return false;
        setPrompt(target);
        return true;
      },
    }),
    [rows],
  );
  return (
    <ProvisioningRecoveryContext.Provider value={recovery}>
      <div className="grid w-settings gap-3 bg-popover p-3.5">
        <SetupOffer action={action} />
      </div>
      <SetupPrompt
        row={prompt}
        onClose={() => setPrompt(null)}
        onSetUp={() => setPrompt(null)}
      />
    </ProvisioningRecoveryContext.Provider>
  );
}

type Args = { shape: SetupShape; action: string };

const meta = {
  title: "Shell/Setup offer",
  args: { shape: "fresh", action: LOCAL_AI_SETUP_ACTION },
  render: (args: Args) => <Screen {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const LocalAiNotSetUp: Story = {};
export const BrowserNotSetUp: Story = {
  args: { action: "operator.provision.browser" },
};
export const LocalAiDamaged: Story = { args: { shape: "partial" } };
/** The computer is below what the local AI needs: it says so, and nothing
 * is offered. */
export const BelowHardware: Story = { args: { shape: "hardware" } };
