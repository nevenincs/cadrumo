import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import {
  CITATION_QUERY,
  NO_MATCH_QUERY,
  referenceCitation,
  referenceFound,
  referenceNothing,
} from "@/dev/fixtures/reference";
import type { ReferenceState } from "../../shell/reference";
import { ReferencePage } from "./ReferencePage";

// Reference in each state it can be shown in: never searched, searching,
// passages with terminology, an exact citation, an answer with no result and
// a search that failed.

const noop = () => undefined;

function Page({ state }: { state: ReferenceState }) {
  const page = useRef<HTMLElement | null>(null);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <ReferencePage
        state={state}
        page={page}
        pane={{ controls: [], onToggleMaximize: noop }}
        onSearch={noop}
      />
    </div>
  );
}

const meta: Meta<typeof Page> = {
  title: "Reference/Page",
  component: Page,
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Page>;

export const NeverSearched: Story = { args: { state: { kind: "idle" } } };
export const Searching: Story = {
  args: { state: { kind: "searching", query: "synthetic" } },
};
export const Passages: Story = {
  args: {
    state: {
      kind: "ready",
      query: "synthetic",
      served: referenceFound("synthetic"),
    },
  },
};
export const ExactCitation: Story = {
  args: {
    state: {
      kind: "ready",
      query: CITATION_QUERY,
      served: referenceCitation(CITATION_QUERY),
    },
  },
};
export const NoResults: Story = {
  args: {
    state: {
      kind: "ready",
      query: NO_MATCH_QUERY,
      served: referenceNothing(NO_MATCH_QUERY),
    },
  },
};
export const Unavailable: Story = {
  args: { state: { kind: "failed", query: "synthetic", code: "timed_out" } },
};
