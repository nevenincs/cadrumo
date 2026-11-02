import type { Meta, StoryObj } from "@storybook/react-vite";
import { EditorSpecimens, namedCodes } from "@/dev/catalogue/EditorSpecimens";
import { currencyName } from "@/shared/codeNames";

/** The codes the ledger serves for the field. */
const CODES = ["EUR", "GBP", "USD", "CHF", "HUF"];

const meta = {
  title: "Editors/Currency",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <EditorSpecimens
      field={{ kind: "currency" }}
      label="Currency"
      filled="EUR"
      invalid="EU"
      offers={namedCodes(CODES, currencyName)}
      error="Not a currency code."
    />
  ),
};
