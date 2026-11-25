import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { operationsFixture } from "@/dev/fixtures/operations";
import type {
  OperationsListing,
  OperationsState,
} from "../../shell/operations";
import { OperationsPage } from "./OperationsPage";

// Operations in each state it can be shown in: reading, unavailable, no runs,
// a list that holds a settling run and an unknown effect, a list that says
// what the journal could not account for, and a list with more to read.

const noop = () => undefined;

function Page({ state }: { state: OperationsState }) {
  const page = useRef<HTMLElement | null>(null);
  return (
    <div className="flex h-full min-h-0 flex-col">
      <OperationsPage
        state={state}
        page={page}
        locale="en"
        pane={{ controls: [], onToggleMaximize: noop }}
        onRefresh={noop}
        onMore={noop}
        onOpen={noop}
      />
    </div>
  );
}

const listing = (
  limit: number,
  options: Parameters<typeof operationsFixture>[2] = {},
): OperationsListing => {
  const served = operationsFixture(limit, null, options);
  return {
    runs: served.runs,
    total: served.run_count,
    unreadable: served.unreadable_records,
    unverifiable: served.unverifiable_records,
    observedAt: served.observed_at,
    next: served.next_cursor,
  };
};

const meta: Meta<typeof Page> = {
  title: "Operations/Page",
  component: Page,
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Page>;

export const Reading: Story = { args: { state: { kind: "loading" } } };
export const Unavailable: Story = {
  args: { state: { kind: "failed", code: "timed_out" } },
};
export const NoRuns: Story = {
  args: {
    state: {
      kind: "ready",
      listing: listing(25, { empty: true }),
      more: { kind: "idle" },
    },
  },
};
export const Runs: Story = {
  args: {
    state: {
      kind: "ready",
      listing: listing(9),
      more: { kind: "idle" },
    },
  },
};
export const MoreToRead: Story = {
  args: {
    state: {
      kind: "ready",
      listing: listing(5),
      more: { kind: "idle" },
    },
  },
};
export const MoreUnavailable: Story = {
  args: {
    state: {
      kind: "ready",
      listing: listing(5),
      more: { kind: "failed", code: "timed_out" },
    },
  },
};
export const RecordsNotAccountedFor: Story = {
  args: {
    state: {
      kind: "ready",
      listing: listing(9, { damaged: true }),
      more: { kind: "idle" },
    },
  },
};
