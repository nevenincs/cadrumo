import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens, namedCodes } from "@/dev/catalogue/EditorSpecimens";
import { countryName } from "@/shared/codeNames";

/** The codes the ledger serves for the field. */
const CODES = ["DE", "ES", "FR", "IT", "PT"];

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
      offers={namedCodes(CODES, countryName)}
      error="Not a country code."
    />
  ),
};
