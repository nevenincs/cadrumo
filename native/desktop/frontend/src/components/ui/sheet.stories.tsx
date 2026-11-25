import type { Meta, StoryObj } from "@storybook/react-vite";
import { Specimen } from "@/dev/catalogue/Frame";
import { Button } from "./button";
import { Field, FieldLabel } from "./field";
import { Input } from "./input";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "./sheet";

const meta = { title: "Primitives/Sheet" } satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

function Example({ side }: { side: "right" | "bottom" }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline">Open from the {side}</Button>
      </SheetTrigger>
      <SheetContent side={side} closeLabel="Close">
        <SheetHeader>
          <SheetTitle>Edit invoice</SheetTitle>
          <SheetDescription>
            Changes stay here until you save them.
          </SheetDescription>
        </SheetHeader>
        <Field>
          <FieldLabel htmlFor={`number-${side}`}>Number</FieldLabel>
          <Input id={`number-${side}`} defaultValue="F-2026-014" />
        </Field>
        <SheetFooter>
          <SheetClose asChild>
            <Button variant="ghost">Cancel</Button>
          </SheetClose>
          <Button>Save</Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export const Sides: Story = {
  render: () => (
    <Specimen
      title="Sheet"
      note="Modal, over a scrim: focus is trapped inside and returns to the opener, and Escape closes it."
    >
      <Example side="right" />
      <Example side="bottom" />
    </Specimen>
  ),
};
