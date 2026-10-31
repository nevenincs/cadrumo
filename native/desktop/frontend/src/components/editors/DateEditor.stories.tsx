import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Specimen } from "@/dev/catalogue/Frame";
import { DateEditor } from "./DateEditor";

const meta = {
  title: "Editors/Date",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

function Held({
  id,
  initial,
  ...rest
}: Omit<Parameters<typeof DateEditor>[0], "value" | "onChange"> & {
  id: string;
  initial: string;
}) {
  const [value, setValue] = useState(initial);
  return <DateEditor id={id} value={value} onChange={setValue} {...rest} />;
}

export const States: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen title="Empty" className="grid">
        <Field>
          <FieldLabel htmlFor="empty">Issued</FieldLabel>
          <Held id="empty" initial="" />
        </Field>
      </Specimen>
      <Specimen title="Filled" className="grid">
        <Field>
          <FieldLabel htmlFor="filled">Issued</FieldLabel>
          <Held id="filled" initial="2026-10-31" />
        </Field>
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Field data-invalid>
          <FieldLabel htmlFor="invalid">Issued</FieldLabel>
          <Held
            id="invalid"
            initial="31/13/2026"
            invalid
            describedBy="invalid-error"
          />
          <FieldError id="invalid-error">No such day.</FieldError>
        </Field>
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Field data-disabled>
          <FieldLabel htmlFor="disabled">Issued</FieldLabel>
          <Held id="disabled" initial="2026-10-31" disabled />
        </Field>
      </Specimen>
      <Specimen title="Limited" className="grid">
        <Field>
          <FieldLabel htmlFor="limited">Issued</FieldLabel>
          <Held
            id="limited"
            initial="2026-10-15"
            min="2026-10-05"
            max="2026-10-25"
          />
        </Field>
      </Specimen>
    </div>
  ),
};
