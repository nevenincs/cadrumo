import type { Meta, StoryObj } from "@storybook/react-vite";
import type { Language } from "./fixtures";
import { Result } from "./Result";
import { languageOf, useFixture } from "./useFixture";

// The result of the return and its settlement, in each served state.

type Which = "failed" | "not_calculated" | "to_pay" | "to_refund";

function Panel({ language, which }: { language: Language; which: Which }) {
  const result = useFixture("result", language);
  if (!result) return null;
  const stated = which === "to_pay" || which === "to_refund";
  const header = stated ? result.stated[which] : result[which].header;
  const fields = stated ? result.failed.fields : result[which].fields;
  return (
    <Result
      header={header}
      fields={fields}
      composed={stated}
      elections={result.export_offer.elections}
      example={stated ? result.elections_303 : undefined}
    />
  );
}

const meta: Meta = {
  title: "Prototypes/Renta/Result",
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

export const CouldNotCalculate: Story = {
  name: "Could not be calculated",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="failed" />
  ),
};

export const NotCalculated: Story = {
  name: "Not calculated yet",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="not_calculated" />
  ),
};

export const ToPay: Story = {
  name: "To pay, settlement questions not served",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="to_pay" />
  ),
};

export const ToRefund: Story = {
  name: "To refund",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="to_refund" />
  ),
};
