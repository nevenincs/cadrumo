import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { STORY_PERIOD } from "@/dev/LedgerStage";
import type { LedgerPeriod } from "../../shell/ledgerGrammar";
import { useStrings } from "../../shell/strings";
import { PeriodSelector } from "./PeriodSelector";

// The period dropdown of the Ledger page, on its own: a quarter, a month, a
// whole year or every period, and the years the ledger holds movements in.

type Args = {
  period?: LedgerPeriod | null;
  years?: number[] | null;
  mode?: "period" | "year";
  allowAll?: boolean;
  open?: boolean;
  locale: string;
};

function Selector({
  period,
  years = [2024, 2025, 2026],
  mode,
  allowAll,
  open,
  locale,
}: Args) {
  const t = useStrings();
  const [value, setValue] = useState<LedgerPeriod | null>(
    period === undefined ? STORY_PERIOD : period,
  );
  return (
    <div className="flex justify-end p-3">
      <PeriodSelector
        value={value}
        onChange={setValue}
        label={t("desktop.ledger.period.label")}
        years={years}
        locale={locale}
        fallbackYear={STORY_PERIOD.year}
        mode={mode}
        allowAll={allowAll}
        open={open}
      />
    </div>
  );
}

const meta: Meta<typeof Selector> = {
  title: "Ledger/Period selector",
  component: Selector,
  render: (args, { globals }) => (
    <Selector {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { surface: "chrome", fill: true },
};
export default meta;
type Story = StoryObj<typeof Selector>;

export const Quarter: Story = {};
export const Month: Story = { args: { period: { year: 2026, code: "10" } } };
export const WholeYear: Story = {
  name: "Whole year",
  args: { period: { year: 2025, code: "0A" } },
};
export const EveryPeriod: Story = {
  name: "Every period",
  args: { period: null },
};
export const Open: Story = { args: { open: true } };
export const OpenOnEveryPeriod: Story = {
  name: "Open, every period",
  args: { open: true, period: null },
};
export const YearsNotKnown: Story = {
  name: "Years not read yet",
  args: { years: null, open: true },
};
export const YearOnly: Story = {
  name: "A year only",
  args: {
    mode: "year",
    allowAll: false,
    open: true,
    period: { year: 2026, code: "0A" },
  },
};
