import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { userEvent } from "storybook/test";
import { Specimen } from "@/dev/catalogue/Frame";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { AgentSettingsPopover } from "./AgentSettingsPopover";
import {
  APPEARANCE_NOTE,
  MODELS,
  PROVIDERS,
  SELECTION,
} from "./Composer.stories";
import type { AgentSelection } from "./types";

// Appearance only. The story holds the selection itself so the controls can
// be tried; nothing reaches a provider.

function Settings({ initial }: { initial: AgentSelection }) {
  const [selection, setSelection] = useState(initial);
  const model = (MODELS[selection.providerId] ?? []).find(
    (option) => option.id === selection.modelId,
  );
  const words = [model?.name, selection.effort].filter(Boolean).join(" · ");
  return (
    <Specimen title="Agent settings" note={APPEARANCE_NOTE}>
      <div className="flex h-dvh w-(--agent-w) items-end pb-24">
        <AgentSettingsPopover
          providers={PROVIDERS}
          models={MODELS}
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

const meta = {
  title: "Shell/Agent/Agent settings popover",
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: { initial: SELECTION },
  render: (args: { initial: AgentSelection }) => <Settings {...args} />,
} satisfies Meta<{ initial: AgentSelection }>;
export default meta;
type Story = StoryObj<typeof meta>;

export const UnselectableProvider: Story = {
  name: "Open, with an unselectable provider",
  play: opened,
};

export const ModelWithoutEfforts: Story = {
  name: "Open, model without efforts",
  args: { initial: { providerId: "anthropic", modelId: "haiku" } },
  play: opened,
};
