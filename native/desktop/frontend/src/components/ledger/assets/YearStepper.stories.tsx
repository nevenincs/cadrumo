import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { REGISTER_DEFAULT_YEAR, REGISTER_YEARS } from "@/dev/assetsRegister";
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
  args: { years: [...REGISTER_YEARS], year: REGISTER_DEFAULT_YEAR },
  argTypes: { years: { table: { disable: true } } },
  parameters: { surface: "chrome", fill: true },
};
export default meta;
type Story = StoryObj<typeof Stepper>;

const listed = REGISTER_YEARS;
/** A year the register lists, left out of the years offered. */
const missing = listed[Math.floor(listed.length / 2)] ?? null;
const first = listed[0] ?? null;

export const EveryListedYear: Story = { name: "Every listed year" };
export const OldestYear: Story = {
  name: "Oldest year",
  args: { year: first },
};
export const NewestYear: Story = {
  name: "Newest year",
  args: { year: listed.at(-1) ?? null },
};
export const NoneChosen: Story = {
  name: "None chosen",
  args: { year: null },
};
export const ChosenYearNotOffered: Story = {
  name: "Chosen year not offered",
  args: { years: listed.filter((year) => year !== missing), year: missing },
};
export const OneYear: Story = {
  name: "One year",
  args: { years: first === null ? [] : [first], year: first },
};
export const NoYears: Story = {
  name: "No years",
  args: { years: [], year: null },
};
