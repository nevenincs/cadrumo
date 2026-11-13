import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { expect, fn, userEvent, waitFor, within } from "storybook/test";
import {
  FIXTURE_END_FIELD,
  FIXTURE_GROUP_KINDS,
  FIXTURE_MISSING_FIELD,
  FIXTURE_REDUCTION_OUTCOMES,
  fixtureOperationId,
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
  type RecordDoorChoice,
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
  const [chosen, setChosen] = useState<RecordDoorChoice | null>(null);
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
          setChosen(choice);
          if (refuseRemoval && choice.action.door === "remove")
            setRefusal({ rowRef: choice.rowRef, refusal: REMOVAL_REFUSED });
        }}
        refusal={refusal}
        onRefusalAction={fn()}
      />
      {chosen !== null && (
        <output
          data-chosen-row={chosen.rowRef}
          data-chosen-operation={chosen.action.operation_definition_id}
          data-chosen-field={chosen.action.field_key ?? ""}
        />
      )}
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
        `[data-record-door="${fixtureOperationId("edit")}"]`,
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
      `[data-record-door="${fixtureOperationId("remove")}"]`,
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

const reductionOf = (root: ParentNode, row: string): HTMLElement =>
  root.querySelector(`[data-record-member="${row}"] [data-record-reduction]`)!;

export const ReductionDetermined: Story = {
  name: "Reduction: each year's served outcome and tier words, each fact's mark",
  render: () => <Owner scenario="reductions" />,
  play: async ({ canvasElement }) => {
    const [applies, doesNotApply] = FIXTURE_REDUCTION_OUTCOMES;
    expect(
      canvasElement.querySelectorAll("[data-record-reduction]"),
    ).toHaveLength(3);
    const lease = reductionOf(canvasElement, "fixture_lease.0");
    expect(lease.querySelector("h5")).toHaveTextContent(
      "Fixture reduction of the lease",
    );
    expect(lease.querySelectorAll("[data-record-reduction-year]")).toHaveLength(
      2,
    );
    expect(
      lease.querySelector(`[data-record-reduction-outcome="${applies}"]`),
    ).not.toBe(null);
    expect(
      lease.querySelector(`[data-record-reduction-outcome="${doesNotApply}"]`),
    ).not.toBe(null);
    expect(lease.querySelectorAll("[data-record-reduction-tier]")).toHaveLength(
      1,
    );
    expect(
      lease.querySelectorAll(
        '[data-record-reduction-fact][data-stated="true"]',
      ),
    ).toHaveLength(2);
    expect(lease.querySelector("[data-record-reduction-missing]")).toBe(null);
  },
};

export const ReductionNotDeterminable: Story = {
  name: "Reduction not determinable: the missing fact and its way out",
  render: () => <Owner scenario="reductions" />,
  play: async ({ canvasElement }) => {
    const lease = reductionOf(canvasElement, "fixture_lease.1");
    expect(
      lease.querySelectorAll(
        '[data-record-reduction-fact][data-stated="false"]',
      ),
    ).toHaveLength(1);
    const missing = lease.querySelector(
      `[data-record-reduction-missing="${FIXTURE_MISSING_FIELD}"]`,
    )!;
    expect(missing).toHaveTextContent("Fixture fact the lease does not state");
    expect(missing.querySelector("[data-record-door]")).toHaveTextContent(
      "Fixture state lease",
    );
    expect(lease.querySelector("[data-record-reduction-tier]")).toBe(null);
  },
};

export const WayOutSubmitsItsField: Story = {
  name: "Way out: the owner receives the served door with the field it opens",
  render: () => <Owner scenario="reductions" />,
  play: async ({ canvasElement }) => {
    await userEvent.click(
      canvasElement.querySelector(
        `[data-record-reduction-missing="${FIXTURE_MISSING_FIELD}"] [data-record-door]`,
      ) as HTMLElement,
    );
    await waitFor(() =>
      expect(canvasElement.querySelector("[data-chosen-row]")).not.toBe(null),
    );
    const chosen = canvasElement.querySelector("[data-chosen-row]")!;
    expect(chosen).toHaveAttribute("data-chosen-field", FIXTURE_MISSING_FIELD);
    expect(chosen).toHaveAttribute("data-chosen-row", "fixture_lease.1");
    expect(chosen).toHaveAttribute(
      "data-chosen-operation",
      fixtureOperationId("edit"),
    );
  },
};

export const OpenLeaseEndDoor: Story = {
  name: "Open lease: its served end door beside the row's own doors",
  render: () => <Owner scenario="reductions" />,
  play: async ({ canvasElement }) => {
    const open = canvasElement.querySelector(
      '[data-record-member="fixture_lease.2"]',
    )!;
    const end = open.querySelector(
      `[data-record-door-field="${FIXTURE_END_FIELD}"]`,
    ) as HTMLElement;
    expect(end).toHaveTextContent("Fixture end lease");
    const closed = canvasElement.querySelector(
      '[data-record-member="fixture_lease.0"]',
    )!;
    expect(
      closed.querySelector(`[data-record-door-field="${FIXTURE_END_FIELD}"]`),
    ).toBe(null);
    await userEvent.click(end);
    await waitFor(() =>
      expect(
        canvasElement.querySelector("[data-chosen-field]"),
      ).toHaveAttribute("data-chosen-field", FIXTURE_END_FIELD),
    );
  },
};

export const ReductionLocked: Story = {
  name: "Reduction locked: the way out and end doors are not usable",
  render: () => <Owner scenario="reductions" writable={false} />,
  play: async ({ canvasElement }) => {
    const fielded = canvasElement.querySelectorAll(
      '[data-record-door-field]:not([data-record-door-field=""])',
    );
    expect(fielded.length).toBeGreaterThan(0);
    fielded.forEach((door) => expect(door).toBeDisabled());
  },
};
