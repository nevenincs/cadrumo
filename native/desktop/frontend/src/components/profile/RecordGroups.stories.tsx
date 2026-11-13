import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { expect, fn, userEvent, waitFor, within } from "storybook/test";
import {
  FIXTURE_GROUP_KINDS,
  fixtureRecordGroupsPage,
  REMOVAL_REFUSED,
  type RecordGroupScenario,
} from "@/dev/profileRecordGroupsFixture";
import {
  acceptRecordGroupsPage,
  emptyStream,
  type RecordGroupStream,
} from "../../shell/profileRecordGroups";
import {
  RecordGroups,
  type RecordGroupsState,
  type RecordRefusal,
} from "./RecordGroups";

// The record groups element over fixture pages of the served read's shape,
// until the host relays `user-profile.record-groups`. Every summary, relation,
// door label, concept and refusal here is plainly invented fixture text; the
// element adds only its chrome. The owner below reads the pages the way the
// profile page will: every kind's first page, then a continuation at a time.

const firstPages = (scenario: RecordGroupScenario): RecordGroupStream[] =>
  FIXTURE_GROUP_KINDS.map((kind) =>
    acceptRecordGroupsPage(
      emptyStream(kind),
      fixtureRecordGroupsPage(scenario, kind, 0),
    ),
  );

function Owner({
  scenario,
  state = "ready",
  refuseRemoval = false,
  writable = true,
}: {
  scenario: RecordGroupScenario;
  state?: RecordGroupsState;
  refuseRemoval?: boolean;
  writable?: boolean;
}) {
  const [streams, setStreams] = useState<RecordGroupStream[]>(() =>
    state === "ready" ? firstPages(scenario) : [],
  );
  const [refusal, setRefusal] = useState<RecordRefusal | null>(null);
  const more = () =>
    setStreams((now) => {
      const at = now.findIndex((stream) => stream.nextCursor !== null);
      const stream = now[at];
      if (!stream || stream.nextCursor === null) return now;
      const next = acceptRecordGroupsPage(
        stream,
        fixtureRecordGroupsPage(scenario, stream.kind, stream.nextCursor),
      );
      return now.map((held, index) => (index === at ? next : held));
    });
  return (
    <div className="max-w-3xl">
      <RecordGroups
        streams={streams}
        state={state}
        writable={writable}
        onMore={more}
        onReadAgain={() => setStreams(firstPages(scenario))}
        onDoor={(choice) => {
          if (refuseRemoval && choice.action.door === "remove")
            setRefusal({ rowRef: choice.rowRef, refusal: REMOVAL_REFUSED });
        }}
        refusal={refusal}
        onRefusalAction={fn()}
      />
    </div>
  );
}

const meta: Meta = {
  title: "Profile/RecordGroups",
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

export const Reading: Story = {
  name: "Reading: nothing read yet",
  render: () => <Owner scenario="none" state="reading" />,
  play: async ({ canvasElement }) => {
    expect(
      canvasElement.querySelector('[data-record-groups="reading"]'),
    ).not.toBe(null);
    expect(canvasElement.querySelector("[data-record-groups-empty]")).toBe(
      null,
    );
  },
};

export const ReadFailed: Story = {
  name: "Read failed: says so and offers a fresh read",
  render: () => <Owner scenario="one_group" state="failed" />,
  play: async ({ canvasElement }) => {
    expect(within(canvasElement).getByRole("alert")).toBeVisible();
    expect(
      canvasElement.querySelector("[data-record-groups-read-again]"),
    ).not.toBe(null);
    expect(canvasElement.querySelectorAll("[data-record-group]")).toHaveLength(
      0,
    );
  },
};

export const NoGroups: Story = {
  name: "No groups: the profile holds no related row",
  render: () => <Owner scenario="none" />,
  play: async ({ canvasElement }) => {
    expect(canvasElement.querySelector("[data-record-groups-empty]")).not.toBe(
      null,
    );
    expect(canvasElement.querySelector("[data-record-groups-more]")).toBe(null);
  },
};

export const OneGroup: Story = {
  name: "One group: members under the row they name, linked ledger rows",
  render: () => <Owner scenario="one_group" />,
  play: async ({ canvasElement }) => {
    const group = canvasElement.querySelector("[data-record-group]")!;
    expect(group).not.toBe(null);
    const nested = group.querySelector(
      '[data-record-parent="fixture_head.1"]',
    ) as HTMLElement;
    expect(nested.style.marginInlineStart).toBe("1.5rem");
    expect(group.querySelectorAll("[data-record-ledger-row]")).toHaveLength(2);
    expect(group.querySelectorAll("[data-record-concept]")).toHaveLength(1);
    expect(
      group.querySelectorAll(
        '[data-record-door="user-profile.repeatable-row-update"]',
      ),
    ).toHaveLength(4);
  },
};

export const Unlinked: Story = {
  name: "Unlinked: no ledger row names the group",
  render: () => <Owner scenario="unlinked" />,
  play: async ({ canvasElement }) => {
    expect(
      canvasElement.querySelectorAll("[data-record-ledger-row]"),
    ).toHaveLength(0);
    expect(canvasElement.querySelector("[data-record-linked-rows] p")).not.toBe(
      null,
    );
  },
};

export const Paged: Story = {
  name: "Paged: the next page continues the group",
  render: () => <Owner scenario="paged" />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    expect(
      canvasElement.querySelectorAll("[data-record-ledger-row]"),
    ).toHaveLength(2);
    const more = canvasElement.querySelector(
      "[data-record-groups-more]",
    ) as HTMLElement;
    await userEvent.click(more);
    await waitFor(() =>
      expect(
        canvasElement.querySelectorAll("[data-record-ledger-row]"),
      ).toHaveLength(6),
    );
    expect(canvasElement.querySelector("[data-record-groups-more]")).toBe(null);
    expect(canvasElement.querySelectorAll("[data-record-group]")).toHaveLength(
      1,
    );
    expect(canvas.queryByRole("alert")).toBe(null);
  },
};

export const StaleContinuation: Story = {
  name: "Stale continuation: the served refusal, then a fresh read",
  render: () => <Owner scenario="stale_continuation" />,
  play: async ({ canvasElement }) => {
    await userEvent.click(
      canvasElement.querySelector("[data-record-groups-more]") as HTMLElement,
    );
    await waitFor(() =>
      expect(
        canvasElement.querySelector("[data-record-groups-refused]"),
      ).not.toBe(null),
    );
    await userEvent.click(
      canvasElement.querySelector(
        "[data-record-groups-read-again]",
      ) as HTMLElement,
    );
    await waitFor(() =>
      expect(canvasElement.querySelector("[data-record-groups-refused]")).toBe(
        null,
      ),
    );
  },
};

export const RemovalRefused: Story = {
  name: "Removal refused: the row operation's refusal on the row",
  render: () => <Owner scenario="one_group" refuseRemoval />,
  play: async ({ canvasElement }) => {
    const member = canvasElement.querySelector(
      '[data-record-member="fixture_head.1"]',
    )!;
    const remove = member.querySelector(
      '[data-record-door="user-profile.repeatable-row-remove"]',
    ) as HTMLElement;
    await userEvent.click(remove);
    await waitFor(() =>
      expect(member.querySelector('[data-slot="refusal-notice"]')).not.toBe(
        null,
      ),
    );
    expect(
      canvasElement.querySelectorAll('[data-slot="refusal-notice"]'),
    ).toHaveLength(1);
  },
};

export const Locked: Story = {
  name: "Locked: doors shown but not usable while the profile cannot be written",
  render: () => <Owner scenario="one_group" writable={false} />,
  play: async ({ canvasElement }) => {
    const doors = canvasElement.querySelectorAll("[data-record-door]");
    expect(doors.length).toBeGreaterThan(0);
    doors.forEach((door) => expect(door).toBeDisabled());
  },
};
