import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useState, type ComponentProps } from "react";
import { userEvent } from "storybook/test";
import { fixtureOfferReads } from "@/dev/agentFixtureModels";
import { agentOffer } from "../../shell/agentOffer";
import { providerStatus } from "../../shell/providerSettings";
import { useStrings } from "../../shell/strings";
import { ProviderSettings } from "./ProviderSettings";
import type { ProviderOutcome, ProviderStatus } from "./types";

// Appearance only: the agent specimen's six made-up providers as the
// settings serve them -- a saved key, an app signed out and one signed in, a
// lane on this computer, an app that is not on this computer, one turned
// off, a lane with many models and a local engine that does not run. Cadrumo
// lists no real providers. Saving, switching and signing in change nothing
// here, and no key is stored or shown.

const READS = fixtureOfferReads();

/** The specimen's lanes, as the settings show them. */
export const PROVIDERS: ProviderStatus[] =
  READS.settings.providers.map(providerStatus);

const NOOP = () => undefined;

type Args = ComponentProps<typeof ProviderSettings>;

/** The settings with the specimen's offer, so a lane on this computer says
 * what the service measured of its engine. */
function Specimen(args: Args) {
  const t = useStrings();
  const offer = useMemo(
    () => agentOffer(t, READS.catalog, READS.lists, READS.settings),
    [t],
  );
  return (
    <div className="w-settings max-w-full">
      <ProviderSettings {...args} lanes={offer.lanes} />
    </div>
  );
}

/** A key save the service refuses while the agent starts: it is on its way
 * for a moment, then answered `busy` with the cause `agent_tree_running`, as
 * the service answers it. */
function AgentStarting(args: Args) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, ProviderOutcome>>({});
  return (
    <Specimen
      {...args}
      busyId={busyId}
      outcomes={outcomes}
      onSave={(id) => {
        setBusyId(id);
        setOutcomes({});
        setTimeout(() => {
          setBusyId(null);
          setOutcomes({
            [id]: {
              kind: "refused",
              code: "busy",
              cause: "agent_tree_running",
              logRef: "0a1b2c3d4e5f",
            },
          });
        }, 300);
      }}
    />
  );
}

/** Opens the details of the lane `id`. */
const expand =
  (id: string): NonNullable<Story["play"]> =>
  async ({ canvasElement }) => {
    const expander = canvasElement.querySelector<HTMLElement>(
      `[data-lane="${id}"] [data-slot=lane-expander]`,
    );
    if (expander) await userEvent.click(expander);
  };

const meta = {
  title: "Shell/Settings/AI providers",
  excludeStories: /^[A-Z][A-Z_]*$/,
  parameters: {
    surface: "chrome",
    docs: {
      description: {
        component:
          "One row per connection: its name and way, one status, whether a conversation leaves this computer, at most one action and the switch, with the reason and its setup behind the expander. The local model controls are shown in Shell/Settings/Local models.",
      },
    },
  },
  args: {
    providers: PROVIDERS,
    onSave: NOOP,
    onTurnOff: NOOP,
    onTurnOn: NOOP,
    onReset: NOOP,
    onRefresh: NOOP,
  },
  render: (args: Args) => <Specimen {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Mixed: Story = {
  name: "Six providers in their states",
};

export const KeySaved: Story = {
  name: "Key saved, checked when first used",
  play: expand("kimi_api"),
};

export const NotConfigured: Story = {
  name: "Not set up: the app is not on this computer",
  play: expand("deepseek_cli"),
};

export const SignedOut: Story = {
  name: "Signed out",
  play: expand("kimi_cli"),
};

export const Off: Story = {
  name: "Off",
  play: expand("antigravity_cli"),
};

export const EngineStopped: Story = {
  name: "Local engine not running",
  play: expand("llamacpp_api"),
};

export const Saving: Story = {
  args: { busyId: "kimi_api" },
};

export const Refused: Story = {
  name: "Change refused, and saved but unread",
  args: {
    outcomes: {
      qwen_api: {
        kind: "refused",
        code: "revision_conflict",
        logRef: "0a1b2c3d4e5f",
      },
      kimi_api: { kind: "saved_unread" },
    },
  },
};

export const Busy: Story = {
  name: "Key save refused while the agent starts",
  render: (args: Args) => <AgentStarting {...args} />,
  play: async (context) => {
    const { canvasElement } = context;
    // A key lane: its stored key is replaced, and the save is refused.
    const row = canvasElement.querySelector<HTMLElement>(
      '[data-lane="qwen_api"]',
    );
    const expander = row?.querySelector<HTMLElement>(
      "[data-slot=lane-expander]",
    );
    if (!row || !expander) return;
    await userEvent.click(expander);
    const replace = row.querySelector<HTMLElement>(
      "[data-slot=lane-details] button",
    );
    if (!replace) return;
    await userEvent.click(replace);
    const field = row.querySelector<HTMLInputElement>("input[type=password]");
    if (!field) return;
    await userEvent.type(field, "FAKE-KEY-not-a-real-key-0000");
    const save = row.querySelector<HTMLElement>("button[type=submit]");
    if (save) await userEvent.click(save);
  },
};
