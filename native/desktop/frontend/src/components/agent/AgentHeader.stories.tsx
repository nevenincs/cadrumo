import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { AgentHeader } from "./AgentHeader";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";

// Appearance only: the header in fixed states. Its toggles report what they
// are given; nothing opens.

type Args = ComponentProps<typeof AgentHeader>;

const meta = {
  title: "Shell/Agent/Agent header",
  parameters: {
    surface: "chrome",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    title: "IVA del tercer trimestre",
    subtitle: "Fixture Deep · High",
    documentCount: 4,
    onNewConversation: NOOP,
    onToggleHistory: NOOP,
    onToggleDocuments: NOOP,
  },
  render: (args: Args) => (
    <div className="grid w-(--agent-w) gap-2">
      <p className="text-xs text-faint">{APPEARANCE_NOTE}</p>
      <AgentHeader {...args} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const HistoryOpen: Story = { args: { historyOpen: true } };

export const DocumentsOpen: Story = { args: { documentsOpen: true } };

export const ManyDocuments: Story = {
  name: "More than 99 documents",
  args: { documentCount: 140 },
};

export const NoDocuments: Story = {
  args: { documentCount: 0, title: "New conversation", subtitle: undefined },
};

export const EveryActionUnavailable: Story = {
  args: {
    onNewConversation: undefined,
    onToggleHistory: undefined,
    onToggleDocuments: undefined,
  },
};
