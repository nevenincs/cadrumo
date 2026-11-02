import type { Meta, StoryObj } from "@storybook/react-vite";
import { Election, type ElectionState } from "./Election";
import type { Language } from "./fixtures";
import { languageOf, useFixture } from "./useFixture";

// The imputation criterion, undeclared and stated, in the setup flow's words.

function Panel({
  language,
  state,
}: {
  language: Language;
  state: ElectionState;
}) {
  const words = useFixture("election", language);
  return words ? <Election words={words} state={state} /> : null;
}

const meta: Meta = {
  title: "Prototypes/Renta/Imputation election",
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

export const Undeclared: Story = {
  name: "Not stated, accrual proposed",
  render: (_, { globals }) => (
    <Panel language={languageOf(globals)} state={{ kind: "undeclared" }} />
  ),
};

export const Stated: Story = {
  name: "Stated for 2025",
  render: (_, { globals }) => (
    <Panel
      language={languageOf(globals)}
      state={{ kind: "stated", value: "devengo", year: 2025 }}
    />
  ),
};
