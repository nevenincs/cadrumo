import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import type { AgentApprovalOption } from "../../shell/agentSession";
import { ApprovalPrompt } from "./ApprovalPrompt";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";

// Appearance only: a decision a reply waits on. Choosing an option does
// nothing here.

type Args = ComponentProps<typeof ApprovalPrompt>;

// As an agent lists them: the card orders them by kind. The agent offers only
// options that answer the call alone.
const EVERY_OPTION: AgentApprovalOption[] = [
  { option_id: "allow-once", name: "Allow this read", kind: "allow_once" },
  { option_id: "reject-once", name: "Skip this read", kind: "reject_once" },
];

const meta = {
  title: "Shell/Agent/Approval prompt",
  parameters: {
    surface: "chrome",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    source: "agent_tool",
    toolCall: "ledger_list",
    toolKind: "read",
    description: "Permission required: ledger_list",
    options: EVERY_OPTION,
    onDecide: NOOP,
  },
  render: (args: Args) => (
    <div className="grid w-(--agent-w) gap-2">
      <ApprovalPrompt {...args} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const ToolCall: Story = {};

export const CadrumoReview: Story = {
  name: "A Cadrumo operation to review",
  args: {
    source: "cadrumo_review",
    toolCall: "Registrar la factura 2026-031",
    description:
      "Añade la factura al libro de ingresos del tercer trimestre: base 1.000,00 €, IVA 210,00 €.",
    options: [
      {
        option_id: "allow-once",
        name: "Registrar la factura",
        kind: "allow_once",
      },
      { option_id: "reject-once", name: "No registrar", kind: "reject_once" },
    ],
  },
};

export const UnnamedOptions: Story = {
  name: "Options the agent gives no name",
  args: {
    toolCall: null,
    description: null,
    options: [
      { option_id: "a", name: "", kind: "allow_once" },
      { option_id: "b", kind: "reject_once" },
      { option_id: "c", name: null, kind: "allow_once" },
      { option_id: "d", name: "   ", kind: "reject_once" },
    ],
  },
};

const LONG_NAME =
  "Allow this read of every entry of the ledger of the third quarter, for this profile, so that the agent can answer the question";

export const LongNames: Story = {
  name: "Names and details at their longest",
  args: {
    toolCall: "ledger_list_every_entry_of_the_third_quarter_of_the_profile_",
    description: "Permission required: ledger_list. ".repeat(40),
    options: [
      { option_id: "allow-once", name: LONG_NAME, kind: "allow_once" },
      { option_id: "reject-once", name: LONG_NAME, kind: "reject_once" },
      { option_id: "reject-once-2", name: "No", kind: "reject_once" },
    ],
  },
};

export const OnlyRememberedOffered: Story = {
  name: "Only options that would be remembered",
  args: {
    options: [
      {
        option_id: "allow-always",
        name: "Allow reads of the ledger from now on",
        kind: "allow_always",
      },
      {
        option_id: "reject-always",
        name: "Never read the ledger",
        kind: "reject_always",
      },
    ],
  },
};

export const RememberedLeftOut: Story = {
  name: "Remembered options beside others are left out",
  args: {
    options: [
      ...EVERY_OPTION,
      {
        option_id: "allow-always",
        name: "Allow reads of the ledger from now on",
        kind: "allow_always",
      },
    ],
  },
};

export const Unavailable: Story = {
  name: "Every option unavailable",
  args: { onDecide: undefined },
};
