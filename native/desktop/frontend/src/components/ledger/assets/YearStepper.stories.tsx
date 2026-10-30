import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { assetFixtureYears } from "@/dev/assetsFixture";
import { YearStepper } from "./YearStepper";

// The year dropdown of the Assets tab, on its own: the years the register
// reports, stepped either side, with no year typed and no bounds of its own.

type Args = { years: number[]; year: number | null };

function Stepper({ years, year }: Args) {
  const [value, setValue] = useState<number | null>(year);
  return (
    <div className="flex p-3">
      <YearStepper value={value} years={years} onChange={setValue} />
    </div>
  );
}

const meta: Meta<typeof Stepper> = {
  title: "Ledger/Assets/Year stepper",
  component: Stepper,
  args: { years: assetFixtureYears(), year: 2024 },
  argTypes: { years: { table: { disable: true } } },
  parameters: { surface: "chrome", fill: true },
};
export default meta;
type Story = StoryObj<typeof Stepper>;

const decades = assetFixtureYears();

export const SpanningDecades: Story = { name: "Spanning decades" };
export const OldestYear: Story = {
  name: "Oldest year",
  args: { year: decades[0] ?? null },
};
export const NewestYear: Story = {
  name: "Newest year",
  args: { year: decades.at(-1) ?? null },
};
export const NoneChosen: Story = {
  name: "None chosen",
  args: { year: null },
};
export const ChosenYearNotOffered: Story = {
  name: "Chosen year not offered",
  args: { years: [2019, 2021, 2024], year: 2022 },
};
export const OneYear: Story = {
  name: "One year",
  args: { years: [2024], year: 2024 },
};
export const NoYears: Story = {
  name: "No years",
  args: { years: [], year: null },
};
