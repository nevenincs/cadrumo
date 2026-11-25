import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Specimen } from "@/dev/catalogue/Frame";
import { TextEditor } from "./TextEditor";

const meta = {
  title: "Editors/Text",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

function Held({
  id,
  initial,
  ...rest
}: Omit<Parameters<typeof TextEditor>[0], "value" | "onChange"> & {
  id: string;
  initial: string;
}) {
  const [value, setValue] = useState(initial);
  return <TextEditor id={id} value={value} onChange={setValue} {...rest} />;
}

export const States: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen title="Default" className="grid">
        <Field>
          <FieldLabel htmlFor="name">Name</FieldLabel>
          <Held id="name" initial="Taller Ferrer" maxLength={80} />
        </Field>
      </Specimen>
      <Specimen title="Code" className="grid">
        <Field>
          <FieldLabel htmlFor="reference">Reference</FieldLabel>
          <Held id="reference" initial="F-2026-014" mono />
        </Field>
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Field data-invalid>
          <FieldLabel htmlFor="email">Email</FieldLabel>
          <Held
            id="email"
            type="email"
            autoComplete="email"
            initial="ana@"
            invalid
            describedBy="email-error"
          />
          <FieldError id="email-error">Enter an email address.</FieldError>
        </Field>
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Field data-disabled>
          <FieldLabel htmlFor="locked">Name</FieldLabel>
          <Held id="locked" initial="Taller Ferrer" disabled />
        </Field>
      </Specimen>
      <Specimen title="Small" className="grid">
        <Field>
          <FieldLabel htmlFor="small">Name</FieldLabel>
          <Held id="small" initial="Taller Ferrer" controlSize="sm" />
        </Field>
      </Specimen>
    </div>
  ),
};
