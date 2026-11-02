import type { Meta, StoryObj } from "@storybook/react-vite";
import { Credits } from "./Credits";
import type { Credits as CreditsData, Language } from "./fixtures";
import { UNRESOLVED_CREDITS } from "./projectV2";
import { languageOf, useFixture } from "./useFixture";

// Withholding and payments on account: unresolved, imported and never
// calculated. No withholding box offers an editor; the register is where
// they are corrected.

function Panel({
  language,
  which,
  projected = false,
}: {
  language: Language;
  which: keyof CreditsData;
  projected?: boolean;
}) {
  const credits = useFixture("credits", language);
  if (!credits) return null;
  return (
    <Credits
      credits={credits[which]}
      projection={projected ? UNRESOLVED_CREDITS : undefined}
    />
  );
}

const meta: Meta = {
  title: "Prototypes/Renta/Credits",
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

export const Unresolved: Story = {
  name: "Salaried, no payer record: unresolved, not zero",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="salaried" />
  ),
};

export const FromRegister: Story = {
  name: "Activity, imported from the register",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="declared_activity" />
  ),
};

export const NotCalculated: Story = {
  name: "Never calculated",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="not_calculated" />
  ),
};

export const ProjectionEstimate: Story = {
  name: "Projection estimate, version 2 tokens without words",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} which="salaried" projected />
  ),
};
