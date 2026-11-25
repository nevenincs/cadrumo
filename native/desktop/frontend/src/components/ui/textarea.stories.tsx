import type { Meta, StoryObj } from "@storybook/react-vite";
import { Specimen } from "@/dev/catalogue/Frame";
import { Field, FieldError, FieldLabel } from "./field";
import { Textarea } from "./textarea";

const meta = {
  title: "Primitives/Textarea",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const States: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen title="Default" className="grid">
        <Field>
          <FieldLabel htmlFor="notes">Notes</FieldLabel>
          <Textarea id="notes" defaultValue={"First line\nSecond line"} />
        </Field>
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Field data-invalid>
          <FieldLabel htmlFor="notes-invalid">Notes</FieldLabel>
          <Textarea id="notes-invalid" aria-invalid defaultValue="Too long" />
          <FieldError>Shorten this.</FieldError>
        </Field>
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Field data-disabled>
          <FieldLabel htmlFor="notes-off">Notes</FieldLabel>
          <Textarea id="notes-off" disabled defaultValue="Locked" />
        </Field>
      </Specimen>
      <Specimen title="Small" className="grid">
        <Textarea controlSize="sm" rows={2} aria-label="Notes" />
      </Specimen>
    </div>
  ),
};
