import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { Button } from "./button";
import { FilterChip } from "./filter-chip";

const meta = { title: "Primitives/Filter chip" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

const FILTERS = ["Category is Rent", "Amount over 100.00", "Unclassified"];

function Chips() {
  const [shown, setShown] = useState(FILTERS);
  return (
    <>
      {shown.map((filter) => (
        <FilterChip
          key={filter}
          removeLabel={`Remove filter: ${filter}`}
          onRemove={() => setShown((now) => now.filter((f) => f !== filter))}
        >
          {filter}
        </FilterChip>
      ))}
      {shown.length < FILTERS.length && (
        <Button variant="link" onClick={() => setShown(FILTERS)}>
          Reset
        </Button>
      )}
    </>
  );
}

export const Filters: Story = {
  render: () => (
    <Specimen
      title="Filters in force"
      note="Each removes itself with a header-sized button named for the filter."
    >
      <Chips />
    </Specimen>
  ),
};
