import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { aeatSyncFixture, type AeatSyncMode } from "@/dev/aeatSyncFixture";
import { aeatSyncResultsFixture } from "@/dev/aeatSyncResultsFixture";
import type { AeatSyncPort } from "../../shell/aeatSync";
import type { AeatSyncResultsPort } from "../../shell/aeatSyncResults";
import { AeatSyncPage } from "./AeatSyncPage";

// The AEAT data page over the scenario port's synthetic status: every area
// state with counts, nothing ever brought, and a status read that fails.

const noop = () => undefined;

function Page({ mode, language }: { mode: AeatSyncMode; language: string }) {
  const page = useRef<HTMLElement | null>(null);
  const port = useRef<AeatSyncPort | null>(null);
  port.current ??= aeatSyncFixture(mode, noop);
  const results = useRef<AeatSyncResultsPort | null>(null);
  results.current ??= aeatSyncResultsFixture("mixed", noop);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <AeatSyncPage
        port={port.current}
        results={results.current}
        reader="synthetic"
        language={language}
        shown
        page={page}
      />
    </div>
  );
}

const meta: Meta<typeof Page> = {
  title: "AEAT data/Overview",
  component: Page,
  render: (args, { globals }) => (
    <Page {...args} language={String(globals.locale ?? "en")} />
  ),
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Page>;

export const Mixed: Story = { args: { mode: "mixed" } };
export const NeverBrought: Story = { args: { mode: "never" } };
export const Unavailable: Story = { args: { mode: "unavailable" } };
