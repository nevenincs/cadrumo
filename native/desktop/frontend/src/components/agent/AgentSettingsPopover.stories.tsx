import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useState } from "react";
import { userEvent } from "storybook/test";
import { Specimen } from "@/dev/catalogue/Frame";
import { FIXTURE_CATALOG } from "@/dev/fixtures/agentCatalog";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { catalogChoices, offeredSelection } from "../../shell/agentCatalog";
import { useStrings } from "../../shell/strings";
import { AgentSettingsPopover } from "./AgentSettingsPopover";
import { APPEARANCE_NOTE } from "./Composer.stories";
import type { AgentSelection } from "./types";

// Appearance only. The choices are deduced from a provider catalog in
// cadrumo-agent's shape: its providers and lanes are cadrumo-agent's own, and
// every model in it is made up. The story holds the selection itself so the
// controls can be tried. Nothing reaches a provider.

function Settings({ start }: { start?: Partial<AgentSelection> }) {
  const t = useStrings();
  const choices = useMemo(() => catalogChoices(t, FIXTURE_CATALOG), [t]);
  const [selection, setSelection] = useState<AgentSelection>(() => ({
    ...(offeredSelection(choices, null) ?? {
      providerId: "",
      wayId: "",
      modelId: "",
    }),
    ...start,
  }));
  const way = choices.providers
    .find((held) => held.id === selection.providerId)
    ?.ways.find((held) => held.id === selection.wayId);
  const model = (choices.models[selection.wayId] ?? []).find(
    (option) => option.id === selection.modelId,
  );
  const effort = (way?.modelWritten?.efforts ?? model?.efforts ?? []).find(
    (held) => held.id === selection.effort,
  );
  const words = [model?.name ?? selection.modelId, effort?.name]
    .filter(Boolean)
    .join(" · ");
  return (
    <Specimen title="Agent settings" note={APPEARANCE_NOTE}>
      <div className="flex h-dvh w-(--agent-w) items-end pb-24">
        <AgentSettingsPopover
          providers={choices.providers}
          models={choices.models}
          selection={selection}
          onChange={setSelection}
        >
          <Button variant="ghost" size="xs">
            {words}
            <Icon name="chevronDown" size="xs" />
          </Button>
        </AgentSettingsPopover>
      </div>
    </Specimen>
  );
}

const opened: NonNullable<Story["play"]> = async ({ canvasElement }) => {
  const trigger = canvasElement.querySelector<HTMLElement>(
    "[aria-haspopup=dialog]",
  );
  if (trigger) await userEvent.click(trigger);
};

type Args = { start?: Partial<AgentSelection> };

const meta = {
  title: "Shell/Agent/Agent settings popover",
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {},
  render: (args: Args) => <Settings {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const EveryProvider: Story = {
  name: "Open, every lane of the catalog",
  play: opened,
};

export const SecondLaneOfOneProvider: Story = {
  name: "Open, the second lane of a provider",
  args: {
    start: {
      providerId: "beta",
      wayId: "beta/cli",
      modelId: "fixture-tiered",
      effort: "medium",
    },
  },
  play: opened,
};

export const NoEffortChosen: Story = {
  name: "Open, the provider's own effort",
  args: {
    start: {
      providerId: "alpha",
      wayId: "alpha/api",
      modelId: "fixture-deep",
      effort: undefined,
    },
  },
  play: opened,
};

export const ModelWithoutEfforts: Story = {
  name: "Open, model without efforts",
  args: {
    start: {
      providerId: "alpha",
      wayId: "alpha/api",
      modelId: "fixture-plain",
      effort: undefined,
    },
  },
  play: opened,
};

export const WrittenModel: Story = {
  name: "Open, a provider that lists no models",
  args: {
    start: { providerId: "gateway", wayId: "gateway/cli", modelId: "" },
  },
  play: opened,
};
