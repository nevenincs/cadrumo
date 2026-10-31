import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";

const meta = {
  title: "Editors/Percent",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "percent", unit: "fraction" }}
      label="Rate"
      filled="0.215"
      invalid="abc"
      error="Not a number."
    />
  ),
};

/** The same text in the other unit: nothing about the unit is hidden. */
export const InPoints: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "percent", unit: "points" }}
      label="Prorrata"
      filled="92.5"
      invalid="abc"
      error="Not a number."
    />
  ),
};
