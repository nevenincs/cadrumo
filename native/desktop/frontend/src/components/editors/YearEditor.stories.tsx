import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens } from "@/dev/catalogue/EditorSpecimens";
import { servedSupport } from "@/dev/servedYearAuthority";

const meta = {
  title: "Editors/Year",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "year" }}
      label="Year"
      filled={String(servedSupport.horizon)}
      invalid="20x6"
      error="Not a year."
    />
  ),
};
