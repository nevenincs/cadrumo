import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";

const meta = {
  title: "Editors/Country",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "country" }}
      label="Country"
      filled="ES"
      invalid="E1"
      error="Not a country code."
    />
  ),
};
