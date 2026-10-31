import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";

const meta = {
  title: "Editors/Date",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "date" }}
      label="Issued"
      filled="2026-10-31"
      invalid="31/13/2026"
      error="No such day."
    />
  ),
};

export const Limited: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "date", min: "2026-10-05", max: "2026-10-25" }}
      label="Issued"
      filled="2026-10-15"
      invalid="31/13/2026"
      error="No such day."
    />
  ),
};
