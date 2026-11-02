import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { useStrings } from "../../shell/strings";
import { Button } from "./button";
import { FilterChip } from "./filter-chip";

const meta = { title: "Primitives/Filter chip" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

// The chips the movements list shows, by their own words.
const FILTER_KEYS = [
  "desktop.ledger.filters.foreign_chip",
  "desktop.ledger.filters.to_match_chip",
  "desktop.ledger.classification.processed_unclassified",
];

function Chips() {
  const t = useStrings();
  const all = FILTER_KEYS.map((key) => t(key));
  const [shown, setShown] = useState(all);
  return (
    <>
      {shown.map((filter) => (
        <FilterChip
          key={filter}
          removeLabel={t("desktop.ledger.filters.remove", { filter })}
          onRemove={() => setShown((now) => now.filter((f) => f !== filter))}
        >
          {filter}
        </FilterChip>
      ))}
      {shown.length < all.length && (
        <Button variant="link" onClick={() => setShown(all)}>
          {t("desktop.ledger.filters.reset")}
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
