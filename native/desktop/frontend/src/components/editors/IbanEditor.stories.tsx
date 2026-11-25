import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";

const meta = {
  title: "Editors/Iban",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "iban" }}
      label="IBAN"
      filled="ES9121000418450200051332"
      invalid="ES92"
      error="This isn't an IBAN."
    />
  ),
};

export const Secret: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "iban", secret: true }}
      label="IBAN"
      filled="ES9121000418450200051332"
      invalid="ES92"
      error="This isn't an IBAN."
    />
  ),
};
