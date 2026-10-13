import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { ApprovalPrompt, type ApprovalOption } from "./ApprovalPrompt";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";

// Appearance only: a decision a reply waits on. Choosing an option does
// nothing here.

type Args = ComponentProps<typeof ApprovalPrompt>;

const EVERY_OPTION: ApprovalOption[] = [
  { id: "allow-once", kind: "allow_once" },
  { id: "allow-always", kind: "allow_always" },
  { id: "reject-once", kind: "reject_once" },
  { id: "reject-always", kind: "reject_always" },
];

const meta = {
  title: "Shell/Agent/Approval prompt",
  parameters: {
    surface: "chrome",
    docs: { description: { component: APPEARANCE_NOTE } },
  },
  args: {
    source: "agent_tool",
    title: "Leer los apuntes del libro",
    description: "Lee los apuntes del tercer trimestre de este perfil.",
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
    title: "Registrar la factura 2026-031",
    description:
      "Añade la factura al libro de ingresos del tercer trimestre: base 1.000,00 €, IVA 210,00 €.",
    options: [
      { id: "allow-once", kind: "allow_once" },
      { id: "reject-once", kind: "reject_once" },
    ],
  },
};

export const Unavailable: Story = {
  name: "Every option unavailable",
  args: { onDecide: undefined },
};
