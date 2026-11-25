import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Specimen } from "@/dev/catalogue/Frame";
import { NotesEditor } from "./NotesEditor";

const meta = {
  title: "Editors/Notes",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

function Held({
  id,
  initial,
  ...rest
}: Omit<Parameters<typeof NotesEditor>[0], "value" | "onChange"> & {
  id: string;
  initial: string;
}) {
  const [value, setValue] = useState(initial);
  return <NotesEditor id={id} value={value} onChange={setValue} {...rest} />;
}

export const States: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen title="Default" className="grid">
        <Field>
          <FieldLabel htmlFor="notes">Notes</FieldLabel>
          <Held id="notes" initial={"Paid by transfer.\nReceipt to follow."} />
        </Field>
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Field data-invalid>
          <FieldLabel htmlFor="notes-invalid">Notes</FieldLabel>
          <Held
            id="notes-invalid"
            initial="Too long"
            invalid
            describedBy="notes-error"
          />
          <FieldError id="notes-error">Shorten this.</FieldError>
        </Field>
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Field data-disabled>
          <FieldLabel htmlFor="notes-off">Notes</FieldLabel>
          <Held id="notes-off" initial="Locked" disabled />
        </Field>
      </Specimen>
    </div>
  ),
};
