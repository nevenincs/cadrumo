import type { Meta, StoryObj } from "@storybook/react-vite";
import { ProviderMark } from "./ProviderMark";
import { PROVIDER_MARKS } from "./providerIcons";

// Appearance only: the marks of the providers cadrumo-agent names, drawn from
// the vendored artwork in providerIcons.ts, and what a provider with no
// artwork gets. The names beside them are the catalog's provider ids.

type Args = { size: "sm" | "md" };

const meta = {
  title: "Shell/Agent/Provider mark",
  parameters: { surface: "card" },
  args: { size: "md" },
  render: ({ size }: Args) => (
    <ul className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
      {Object.keys(PROVIDER_MARKS).map((provider) => (
        <li key={provider} className="flex items-center gap-2 text-base">
          <ProviderMark provider={provider} size={size} />
          <span>{provider}</span>
        </li>
      ))}
      <li className="flex items-center gap-2 text-base">
        <ProviderMark provider="not-in-the-catalog" size={size} />
        <span>No artwork</span>
      </li>
    </ul>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Marks: Story = {};

export const Small: Story = { args: { size: "sm" } };
