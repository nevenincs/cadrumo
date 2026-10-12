import type { Meta, StoryObj } from "@storybook/react-vite";
import { AgentWelcome } from "./AgentWelcome";
import { APPEARANCE_NOTE } from "./Composer.stories";

// Appearance only: what an empty conversation shows.

const meta = {
  title: "Shell/Agent/Agent welcome",
  parameters: {
    fill: true,
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  render: () => (
    <div className="flex h-dvh w-(--agent-w) flex-col border-r bg-background">
      <p className="px-4 pt-4 text-xs text-faint">{APPEARANCE_NOTE}</p>
      <AgentWelcome />
    </div>
  ),
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const Welcome: Story = {};
