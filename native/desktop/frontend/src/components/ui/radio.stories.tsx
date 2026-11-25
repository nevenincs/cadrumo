import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { RadioGroup, RadioGroupItem } from "./radio";

const meta = {
  title: "Primitives/Radio",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

const OPTIONS = ["Invoice 2026-014", "Invoice 2026-015", "Invoice 2026-016"];

function Options({
  disabled,
  invalid,
}: {
  disabled?: boolean;
  invalid?: boolean;
}) {
  const [value, setValue] = useState(OPTIONS[0]);
  return (
    <RadioGroup
      aria-label="Invoice"
      value={value}
      onValueChange={setValue}
      disabled={disabled}
    >
      {OPTIONS.map((option) => (
        <label
          key={option}
          className="flex cursor-pointer items-center gap-2 text-sm"
        >
          <RadioGroupItem value={option} aria-invalid={invalid || undefined} />
          <span>{option}</span>
        </label>
      ))}
    </RadioGroup>
  );
}

export const States: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen
        title="Default"
        note="One tab stop; arrow keys move the choice."
        className="grid"
      >
        <Options />
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Options invalid />
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Options disabled />
      </Specimen>
    </div>
  ),
};
