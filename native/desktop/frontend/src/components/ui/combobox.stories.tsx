import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { SAMPLE_CATEGORIES, categoryLabel } from "@/dev/primitives/gridSample";
import { Button } from "./button";
import { Combobox } from "./combobox";
import { Icon } from "./icon";

const meta = { title: "Primitives/Combobox" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

function Choice({ error }: { error?: string }) {
  const [value, setValue] = useState<string | null>("rent");
  return (
    <Combobox
      label="Category"
      value={value}
      options={SAMPLE_CATEGORIES}
      emptyLabel="No category matches"
      placeholder="Search categories"
      hint="Families group the categories."
      error={error}
      onCommit={(next) => setValue(next)}
      footer={
        <Button variant="ghost" size="sm" className="w-full justify-start">
          <Icon name="settings" />
          Manage categories
        </Button>
      }
    >
      <Button variant="outline" className="w-field justify-between">
        {categoryLabel(value)}
        <Icon name="chevronDown" />
      </Button>
    </Combobox>
  );
}

export const Searchable: Story = {
  render: () => (
    <div>
      <Specimen
        title="Searchable choice"
        note="Grouped options, a disabled one with its reason, a hint and a footer. Enter chooses, Tab chooses and moves on, Escape leaves the value."
      >
        <Choice />
      </Specimen>
      <Specimen title="Refused" note="The error is read with the field.">
        <Choice error="This category does not apply to the period." />
      </Specimen>
    </div>
  ),
};
