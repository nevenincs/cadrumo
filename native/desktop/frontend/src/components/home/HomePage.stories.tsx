import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import {
  EMPTY_HOME,
  FIXTURE_HOME,
  PARTIAL_HOME,
  UNAVAILABLE_HOME,
} from "@/dev/fixtures/home";
import type { HomeState } from "../../shell/home";
import { HomePage } from "./HomePage";

// Home in each state it can be shown in: every zone with its data, zones in
// each standing that is not showing data, zones known to be empty, Home as a
// whole unavailable, a read in flight and a read that failed.

const noop = () => undefined;

function Page({ state, language }: { state: HomeState; language: string }) {
  const page = useRef<HTMLElement | null>(null);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <HomePage
        state={state}
        locale={language}
        page={page}
        pane={{ controls: [], onToggleMaximize: noop }}
        onRefresh={noop}
        onOpen={noop}
      />
    </div>
  );
}

const meta: Meta<typeof Page> = {
  title: "Home/Page",
  component: Page,
  render: (args, { globals }) => (
    <Page {...args} language={String(globals.locale ?? "en")} />
  ),
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Page>;

export const Ready: Story = {
  args: { state: { kind: "ready", home: FIXTURE_HOME } },
};
export const ZonesNotShowingData: Story = {
  args: { state: { kind: "ready", home: PARTIAL_HOME } },
};
export const ZonesKnownEmpty: Story = {
  args: { state: { kind: "ready", home: EMPTY_HOME } },
};
export const Unavailable: Story = {
  args: { state: { kind: "ready", home: UNAVAILABLE_HOME } },
};
export const Loading: Story = { args: { state: { kind: "loading" } } };
export const Failed: Story = {
  args: { state: { kind: "failed", code: "timed_out" } },
};
