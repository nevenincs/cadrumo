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
// cadrumo-agent's shape, every model in it made up; the story holds the
// selection itself so the controls can be tried. Nothing reaches a provider.

function Settings({ start }: { start?: Partial<AgentSelection> }) {
  const t = useStrings();
  const choices = useMemo(() => catalogChoices(t, FIXTURE_CATALOG), [t]);
  const [selection, setSelection] = useState<AgentSelection>(() => ({
    ...(offeredSelection(choices, null) ?? { providerId: "", modelId: "" }),
    ...start,
  }));
  const model = (choices.models[selection.providerId] ?? []).find(
    (option) => option.id === selection.modelId,
  );
  const effort = model?.efforts.find((held) => held.id === selection.effort);
  const words = [model?.name, effort?.name].filter(Boolean).join(" · ");
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

export const EveryLane: Story = {
  name: "Open, every lane of the catalog",
  play: opened,
};

export const ModelSettings: Story = {
  name: "Open, a model with its own setting",
  args: {
    start: {
      providerId: "openai openai-api",
      modelId: "fixture-tiered",
      effort: "medium",
      controls: { service_tier: "standard" },
    },
  },
  play: opened,
};

export const ModelWithoutEfforts: Story = {
  name: "Open, model without efforts",
  args: {
    start: {
      providerId: "anthropic anthropic-api",
      modelId: "fixture-plain",
      effort: undefined,
    },
  },
  play: opened,
};
