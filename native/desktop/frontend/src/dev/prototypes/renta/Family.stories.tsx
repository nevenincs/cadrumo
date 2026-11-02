import type { Meta, StoryObj } from "@storybook/react-vite";
import { Family } from "./Family";
import type { Language } from "./fixtures";
import { languageOf, useFixture } from "./useFixture";

// The family unit: the served profile facts beside the minimum boxes.

function Panel({ language }: { language: Language }) {
  const family = useFixture("family", language);
  return family ? <Family family={family} /> : null;
}

const meta: Meta = {
  title: "Prototypes/Renta/Family",
  parameters: { layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

export const ProfileAndMinimums: Story = {
  name: "Profile facts and the minimum boxes they feed",
  render: (_, { globals }) => <Panel language={languageOf(globals)} />,
};
