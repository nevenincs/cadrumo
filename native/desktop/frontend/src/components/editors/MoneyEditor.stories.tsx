import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";

const meta = {
  title: "Editors/Money",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "money" }}
      label="Amount"
      filled="1234567.5"
      invalid="1.234"
      error="Could be read two ways."
    />
  ),
};
