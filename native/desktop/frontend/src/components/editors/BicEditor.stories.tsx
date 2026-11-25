import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";

const meta = {
  title: "Editors/Bic",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "bic" }}
      label="BIC"
      filled="CAIXESBBXXX"
      invalid="CAIX"
      error="This isn't a BIC."
    />
  ),
};
