import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ComponentProps } from "react";
import { APPEARANCE_NOTE, NOOP } from "./Composer.stories";
import { ConsentPrompt } from "./ConsentPrompt";

// Appearance only, and a proposal: the wording and the flow of this prompt
// need the owner's review before it is used. Nothing is sent or withheld
// here; Allow and Decline do nothing.

const REVIEW_NOTE = `Needs owner review: proposed consent wording and flow. ${APPEARANCE_NOTE}`;

type Args = ComponentProps<typeof ConsentPrompt>;

const meta = {
  title: "Shell/Agent/Consent prompt",
  parameters: {
    surface: "chrome",
    docs: { description: { component: REVIEW_NOTE } },
  },
  args: {
    providerName: "Example Alpha",
    modelName: "Fixture Deep",
    contentItems: [
      { id: "message", label: "Your message" },
      {
        id: "documents",
        label:
          "3 documents: factura-2026-031.pdf, factura-luz.png, extracto-tercer-trimestre.xlsx",
      },
      {
        id: "tools",
        label: "Results from Cadrumo tools in this conversation",
      },
    ],
    onAllow: NOOP,
    onDecline: NOOP,
  },
  render: (args: Args) => (
    <div className="grid w-(--agent-w) gap-2">
      <p className="text-xs text-faint">{REVIEW_NOTE}</p>
      <ConsentPrompt {...args} />
    </div>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const BeforeSending: Story = { name: "Before sending (needs review)" };

export const MessageOnly: Story = {
  name: "Message only (needs review)",
  args: { contentItems: [{ id: "message", label: "Your message" }] },
};

export const Unavailable: Story = {
  name: "Allow and Decline unavailable (needs review)",
  args: { onAllow: undefined, onDecline: undefined },
};
