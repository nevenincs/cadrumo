import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { Specimen } from "@/dev/catalogue/Frame";
import { Field, FieldDescription, FieldError, FieldLabel } from "./field";
import { Input } from "./input";
import { PasswordInput } from "./password-input";
import { SegmentedControl, SegmentedControlItem } from "./segmented-control";

const meta = {
  title: "Primitives/Field",
  parameters: { surface: "card" },
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

function Password(props: { invalid?: boolean; disabled?: boolean }) {
  const [revealed, setRevealed] = useState(false);
  return (
    <PasswordInput
      id={`password-${props.invalid ? "invalid" : props.disabled ? "off" : "on"}`}
      revealed={revealed}
      onRevealedChange={setRevealed}
      showLabel="Show password"
      hideLabel="Hide password"
      aria-invalid={props.invalid || undefined}
      disabled={props.disabled}
      defaultValue={props.invalid ? "not-it" : undefined}
    />
  );
}

export const TextInput: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen title="Default" className="grid">
        <Field>
          <FieldLabel htmlFor="filter">Filter</FieldLabel>
          <Input id="filter" placeholder="Filter records" />
          <FieldDescription>Matches logger and message.</FieldDescription>
        </Field>
      </Specimen>
      <Specimen title="Invalid" className="grid">
        <Field data-invalid>
          <FieldLabel htmlFor="invalid">Profile name</FieldLabel>
          <Input id="invalid" aria-invalid defaultValue="   " />
          <FieldError>Enter a name.</FieldError>
        </Field>
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <Field data-disabled>
          <FieldLabel htmlFor="disabled">Filter</FieldLabel>
          <Input id="disabled" disabled placeholder="Filter records" />
        </Field>
      </Specimen>
      <Specimen title="Toolbar size" className="grid">
        <Input
          controlSize="sm"
          aria-label="Filter"
          placeholder="Filter records"
        />
      </Specimen>
    </div>
  ),
};

export const PasswordField: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen
        title="Password"
        note="A native password input: paste and password managers work."
        className="grid"
      >
        <Field>
          <FieldLabel htmlFor="password-on">Password</FieldLabel>
          <Password />
        </Field>
      </Specimen>
      <Specimen title="Refused" className="grid">
        <Field data-invalid>
          <FieldLabel htmlFor="password-invalid">Password</FieldLabel>
          <Password invalid />
          <FieldError>That password didn't work. Try again.</FieldError>
        </Field>
      </Specimen>
      <Specimen title="Pending or unavailable" className="grid">
        <Field data-disabled>
          <FieldLabel htmlFor="password-off">Password</FieldLabel>
          <Password disabled />
        </Field>
      </Specimen>
    </div>
  ),
};

function Choice() {
  const [value, setValue] = useState("follow");
  return (
    <Field>
      <FieldLabel id="appearance">Appearance</FieldLabel>
      <SegmentedControl
        aria-labelledby="appearance"
        value={value}
        onValueChange={setValue}
      >
        <SegmentedControlItem value="follow">Follow docs</SegmentedControlItem>
        <SegmentedControlItem value="light">Light</SegmentedControlItem>
        <SegmentedControlItem value="dark">Dark</SegmentedControlItem>
      </SegmentedControl>
    </Field>
  );
}

export const Segmented: Story = {
  render: () => (
    <div className="max-w-80">
      <Specimen
        title="Segmented control"
        note="A radio group: one tab stop, arrow keys move the choice."
        className="grid"
      >
        <Choice />
      </Specimen>
      <Specimen title="Disabled" className="grid">
        <SegmentedControl aria-label="Terminal text" value="13" disabled>
          <SegmentedControlItem value="12">12</SegmentedControlItem>
          <SegmentedControlItem value="13">13</SegmentedControlItem>
          <SegmentedControlItem value="14">14</SegmentedControlItem>
        </SegmentedControl>
      </Specimen>
    </div>
  ),
};
