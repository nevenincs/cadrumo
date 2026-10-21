import type { Meta, StoryObj } from "@storybook/react-vite";
import { ProviderMark } from "./ProviderMark";

// Appearance only: the neutral mark every provider gets. The ids are made up;
// Cadrumo keeps no artwork of any provider.

type Args = { size: "sm" | "md" };

const meta = {
  title: "Shell/Agent/Provider mark",
  parameters: { surface: "card" },
  args: { size: "md" },
  render: ({ size }: Args) => (
    <ul className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
      {["example_one", "example_two", "example_three"].map((provider) => (
        <li key={provider} className="flex items-center gap-2 text-base">
          <ProviderMark provider={provider} size={size} />
          <span>{provider}</span>
        </li>
      ))}
    </ul>
  ),
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Marks: Story = {};

export const Small: Story = { args: { size: "sm" } };
