import { useState } from "react";
import { Button } from "@/components/ui/button";
import { FilterChip } from "@/components/ui/filter-chip";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

const FILTERS = ["Category is Rent", "Amount over 100.00"];

/** The grid's companions over made-up content: a sheet from the right and
 * the filters in force. */
export function CompanionsHarness() {
  const [filters, setFilters] = useState(FILTERS);
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {filters.map((filter) => (
          <FilterChip
            key={filter}
            removeLabel={`Remove filter: ${filter}`}
            onRemove={() =>
              setFilters((now) => now.filter((entry) => entry !== filter))
            }
          >
            {filter}
          </FilterChip>
        ))}
      </div>
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="outline" className="w-fit">
            Edit invoice
          </Button>
        </SheetTrigger>
        <SheetContent closeLabel="Close">
          <SheetHeader>
            <SheetTitle>Edit invoice</SheetTitle>
            <SheetDescription>
              Changes stay here until you save them.
            </SheetDescription>
          </SheetHeader>
          <SheetFooter>
            <SheetClose asChild>
              <Button variant="ghost">Cancel</Button>
            </SheetClose>
            <Button>Save</Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
