import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";

const meta = {
  title: "Editors/TaxId",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "taxId" }}
      label="Tax id"
      filled="B12345678"
      invalid="?"
      error="Not a tax id."
    />
  ),
};
