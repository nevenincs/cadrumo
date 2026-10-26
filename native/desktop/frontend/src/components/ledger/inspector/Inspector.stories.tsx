import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import {
  STORY_PERIOD,
  STORY_READER,
  storyMovementIds,
  useLedgerPort,
  useLedgerRead,
  useStoryStage,
} from "@/dev/LedgerStage";
import type { LedgerRow } from "../../../shell/ledger";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import { MatchQueue } from "../matching/MatchQueue";
import { useSealedMovements } from "../useSealedMovements";
import { ActionDialog, type ActionRequest } from "./ActionDialog";
import { LedgerInspector } from "./LedgerInspector";
import type { SectionInspectorContext } from "./inspectorContext";
import type { InspectorFocus } from "./MovementInspector";
import type { RightPanelMode } from "./RightPanel";
import { SplitDialog } from "./SplitDialog";

// The panel beside the movements grid, over the movements the scenario's
// ledger holds: one movement, several, none, and the queue of movements to
// match. The dialogs it opens for a split and for a lifecycle change or
// removal follow.

const noop = () => undefined;
const NOT_FOCUSED: InspectorFocus = { section: null, index: false, tick: 0 };

type Args = {
  /** The movements selected, by id. */
  selected?: string[];
  period?: LedgerPeriod;
  mode?: RightPanelMode;
  locale: string;
};

function Inspector({
  selected = [],
  period = STORY_PERIOD,
  mode = "movement",
  locale,
}: Args) {
  const port = useLedgerPort();
  const read = useLedgerRead(port, period);
  const { stage, onStage } = useStoryStage();
  const [selection, setSelection] = useState<ReadonlySet<string>>(
    () => new Set(selected),
  );
  const [panelMode, setPanelMode] = useState(mode);
  const [width, setWidth] = useState<number | null>(null);
  const { sealed, unread } = useSealedMovements(
    port,
    STORY_READER,
    read.generation,
    [...selection],
  );
  const context: SectionInspectorContext | null = read.rows
    ? {
        visible: new Set(
          read.rows.map((row) => row.transaction.transaction_id),
        ),
        partial: false,
        checked: read.sets.checked,
        issues: read.sets.issues,
        accounts: null,
        duplicates: new Set(),
        classify: noop,
        focusActive: noop,
        showHidden: noop,
      }
    : null;
  return (
    <div className="flex h-full min-h-0 justify-end">
      {read.rows && read.window && (
        <LedgerInspector
          port={port}
          reader={STORY_READER}
          rows={read.rows}
          generation={read.window.generation}
          stage={stage}
          onStage={onStage}
          sealed={sealed}
          unread={unread}
          selection={selection}
          onSelection={setSelection}
          context={context}
          mode={panelMode}
          onMode={setPanelMode}
          matchPanel={
            <MatchQueue
              port={port}
              reader={STORY_READER}
              shown={panelMode === "match"}
              rows={read.rows}
              generation={read.generation}
              stage={stage}
              onStage={onStage}
              onChoose={(id) => {
                setSelection(new Set([id]));
                setPanelMode("movement");
              }}
              locale={locale}
            />
          }
          width={width}
          onWidth={setWidth}
          focus={NOT_FOCUSED}
          locale={locale}
          onClose={noop}
          onOpenInvoice={noop}
          onExport={noop}
          onMakeRule={noop}
          copy={async () => undefined}
        />
      )}
    </div>
  );
}

const meta: Meta<typeof Inspector> = {
  title: "Ledger/Inspector",
  component: Inspector,
  render: (args, { globals }) => (
    <Inspector {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Inspector>;

export const NothingSelected: Story = {
  name: "Nothing selected",
};
export const Personal: Story = {
  name: "A personal movement",
  args: {
    selected: storyMovementIds(
      (m) =>
        m.transaction.direction === "OUTGOING" &&
        m.transaction.business_classification === "PERSONAL",
      1,
    ),
  },
};
export const Business: Story = {
  name: "A business movement",
  args: {
    selected: storyMovementIds(
      (m) =>
        m.transaction.business_classification === "BUSINESS" &&
        m.transaction.category_id !== null,
      1,
    ),
  },
};
export const LinkedToInvoice: Story = {
  name: "A movement linked to an invoice",
  args: {
    selected: storyMovementIds((m) => m.transaction.invoice_id !== null, 1),
  },
};
export const Mixed: Story = {
  name: "A mixed movement",
  args: {
    selected: storyMovementIds(
      (m) => m.transaction.business_classification === "MIXED",
      1,
    ),
  },
};
export const ToClassify: Story = {
  name: "A movement still to classify",
  args: {
    selected: storyMovementIds(
      (m) => m.transaction.business_classification === "NOT_YET_PROCESSED",
      1,
    ),
  },
};
export const Foreign: Story = {
  name: "A movement in a foreign currency",
  args: {
    selected: storyMovementIds((m) => m.transaction.currency !== "EUR", 1),
  },
};
export const Transfer: Story = {
  name: "A transfer between own accounts",
  args: {
    selected: storyMovementIds(
      (m) => m.transaction.direction === "INTERNAL_TRANSFER",
      1,
    ),
  },
};
export const Sealed: Story = {
  name: "A movement a filed declaration cites",
  args: {
    period: { year: 2026, code: "1T" },
    selected: storyMovementIds(
      (m) => m.sealed && m.transaction.direction === "OUTGOING",
      1,
      ["2026-01", "2026-02", "2026-03"],
    ),
  },
};
export const Several: Story = {
  name: "Several movements",
  args: {
    selected: storyMovementIds(
      (m) => m.transaction.business_classification === "NOT_YET_PROCESSED",
      4,
    ),
  },
};
export const ToMatch: Story = {
  name: "The queue of movements to match",
  args: { mode: "match" },
};

type SplitArgs = { id?: string };

function Split({ id }: SplitArgs) {
  const port = useLedgerPort();
  const read = useLedgerRead(port);
  const row: LedgerRow | undefined =
    read.rows?.find((found) => found.transaction.transaction_id === id) ??
    read.rows?.find(
      (found) => found.transaction.business_classification === "BUSINESS",
    );
  return row ? (
    <SplitDialog
      row={row}
      locale="en"
      onStage={noop}
      onClose={noop}
      say={noop}
    />
  ) : null;
}

export const SplitMovement: StoryObj<SplitArgs> = {
  name: "Split a movement",
  render: (args) => <Split {...args} />,
};

type ActionArgs = {
  request: (ids: string[]) => ActionRequest;
  ids: string[];
  period?: LedgerPeriod;
};

function Action({ request, ids, period }: ActionArgs) {
  const port = useLedgerPort();
  const read = useLedgerRead(port, period);
  const { sealed } = useSealedMovements(
    port,
    STORY_READER,
    read.generation,
    ids,
  );
  const rows = new Map(
    (read.rows ?? []).map((row) => [row.transaction.transaction_id, row]),
  );
  return read.rows ? (
    <ActionDialog
      port={port}
      request={request(ids)}
      rows={rows}
      sealed={sealed}
      onStage={noop}
      onClose={noop}
      say={noop}
    />
  ) : null;
}

const action = (
  request: ActionArgs["request"],
  ids = storyMovementIds(
    (m) =>
      m.transaction.business_classification === "PERSONAL" &&
      m.transaction.direction === "OUTGOING",
    2,
  ),
  period?: LedgerPeriod,
): StoryObj<ActionArgs> => ({
  args: { request, ids, period },
  render: (args) => <Action {...args} />,
});

export const ActionArchive: StoryObj<ActionArgs> = {
  name: "Archive movements",
  ...action((ids) => ({ kind: "archive", ids })),
};
export const ActionExclude: StoryObj<ActionArgs> = {
  name: "Exclude movements",
  ...action((ids) => ({ kind: "exclude", ids, reason: "Paid twice" })),
};
export const ActionRemove: StoryObj<ActionArgs> = {
  name: "Remove a movement",
  ...action(
    (ids) => ({ kind: "remove", id: ids[0] ?? "" }),
    [...storyMovementIds((m) => m.transaction.invoice_id === null, 1)],
  ),
};
export const ActionRemoveSealed: StoryObj<ActionArgs> = {
  name: "Remove a movement a filed declaration cites",
  ...action(
    (ids) => ({ kind: "remove", id: ids[0] ?? "" }),
    storyMovementIds(
      (m) => m.sealed && m.transaction.direction === "OUTGOING",
      1,
      ["2026-01", "2026-02", "2026-03"],
    ),
    { year: 2026, code: "1T" },
  ),
};
export const ActionMerge: StoryObj<ActionArgs> = {
  name: "Merge movements",
  ...action((ids) => ({ kind: "merge", ids })),
};
