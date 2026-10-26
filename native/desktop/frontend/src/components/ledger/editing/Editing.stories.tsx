import type { Meta, StoryObj } from "@storybook/react-vite";
import { useEffect, useRef } from "react";
import { userEvent, waitFor } from "storybook/test";
import {
  STORY_READER,
  useLedgerPort,
  useLedgerRead,
  useStoryStage,
} from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { StageCell } from "../../../shell/ledgerStage";
import { PausedBanner, usePagePause, WritePauseContext } from "../WritePause";
import { useSealedMovements } from "../useSealedMovements";
import { ChangesTray } from "./ChangesTray";
import { LeaveDialog } from "./LeaveDialog";
import { useLedgerEditing } from "./LedgerEditing";
import { PasteDialog } from "./PasteDialog";
import { stageTally, type PastePlan } from "./editingModel";

// What is staged and not yet saved: the tray at the foot of the page, the
// review that checks it against the ledger and saves it, the guard before
// leaving, and the paste preview. The review is the page's own, driven by
// changes staged on the scenario's ledger.

const noop = () => undefined;

type StagedArgs = {
  shape?: LedgerShape;
  /** How many movements get a changed description. */
  edits?: number;
  locale: string;
};

function Staged({ shape, edits = 2, locale }: StagedArgs) {
  const port = useLedgerPort(shape);
  const read = useLedgerRead(port);
  const { stage, onStage } = useStoryStage();
  const pause = usePagePause({
    reader: STORY_READER,
    afterReread: read.reread,
  });
  const { sealedOf } = useSealedMovements(
    port,
    STORY_READER,
    read.generation,
    [],
  );
  const editing = useLedgerEditing({
    port,
    period: read.window?.period ?? null,
    rows: read.rows,
    stage,
    dispatch: onStage,
    reread: read.reread,
    onRekey: noop,
    onShowRows: noop,
    onGoToDraft: noop,
    locale,
    pause,
    sealedOf,
  });
  // The changes are staged once, on the first movements read.
  const seeded = useRef(false);
  useEffect(() => {
    if (seeded.current || !read.rows || read.rows.length === 0) return;
    seeded.current = true;
    const cells: StageCell[] = read.rows.slice(0, edits).map((row) => ({
      id: row.transaction.transaction_id,
      field: "notes",
      value: { kind: "set", value: "Checked against the statement" },
      stored: row.transaction.notes,
    }));
    editing.onStage({ type: "stage", label: "set", cells });
  }, [read.rows, edits, editing]);
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="flex h-full min-h-0 flex-col justify-end">
        <PausedBanner pause={pause} onShow={noop} />
        {editing.dock}
      </div>
    </WritePauseContext.Provider>
  );
}

const opened =
  (selector: string): NonNullable<StoryObj["play"]> =>
  async ({ canvasElement }) => {
    const found = await waitFor(() => {
      const button = canvasElement.querySelector<HTMLElement>(selector);
      if (!button) throw new Error(`${selector} is not drawn yet`);
      return button;
    });
    await userEvent.click(found);
  };

const meta: Meta<typeof Staged> = {
  title: "Ledger/Editing",
  component: Staged,
  render: (args, { globals }) => (
    <Staged {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Staged>;

export const StagedTray: Story = {
  name: "Changes staged",
};
export const StagedTrayOpen: Story = {
  name: "Changes staged, tray open",
  play: opened(".ledger-tray-toggle"),
};
export const Review: Story = {
  name: "Review before saving",
  play: opened(".ledger-tray-review"),
};
export const ReviewRefused: Story = {
  name: "Review, writes refused",
  args: { shape: "refused" },
  play: opened(".ledger-tray-review"),
};
type Outcome = "unknown" | "lost" | "saved_unread" | "refused";

/** Reviews the staged changes and saves them while the made-up ledger answers
 * the next write as `outcome`. */
const saved =
  (outcome?: Outcome): NonNullable<StoryObj["play"]> =>
  async (context) => {
    if (outcome) window.__scenarioLedger?.nextWrites([outcome]);
    await opened(".ledger-tray-review")(context);
    const body = context.canvasElement.ownerDocument.body;
    const save = await waitFor(() => {
      const found = body.querySelector<HTMLElement>(
        ".ledger-apply-save:not([aria-disabled=true])",
      );
      if (!found) throw new Error("the save button is not ready yet");
      return found;
    });
    await userEvent.click(save);
  };

export const SaveDone: Story = {
  name: "Saved",
  play: saved(),
};
export const SaveNotSeen: Story = {
  name: "Saved, settlement not seen",
  play: saved("unknown"),
};
export const SaveAnswerLost: Story = {
  name: "Saved, answer lost",
  play: saved("saved_unread"),
};
export const SaveRefusedByLedger: Story = {
  name: "Save refused",
  play: saved("refused"),
};

type TrayArgs = { paused?: string | null; canUndo?: boolean };

function Tray({ paused = null, canUndo = true }: TrayArgs) {
  return (
    <div className="flex h-full flex-col justify-end">
      <ChangesTray
        tally={stageTally({
          rows: {
            a: { notes: { kind: "set", value: "x" } },
            b: {
              notes: { kind: "set", value: "y" },
              category_id: { kind: "clear" },
            },
          },
          drafts: [{ key: "d", idempotencyKey: "k", fields: {} }],
          actions: [],
        })}
        paused={paused}
        canUndo={canUndo}
        onUndo={noop}
        onDiscard={noop}
        onReview={noop}
      />
    </div>
  );
}

export const TrayAtRest: StoryObj<TrayArgs> = {
  name: "Tray",
  render: (args) => <Tray {...args} />,
};
export const TrayPaused: StoryObj<TrayArgs> = {
  name: "Tray, writes paused",
  args: { paused: "A write was not seen to settle" },
  render: (args) => <Tray {...args} />,
  play: opened(".ledger-tray-toggle"),
};

export const Leaving: StoryObj = {
  name: "Leaving with changes staged",
  render: () => (
    <LeaveDialog units={5} onReview={noop} onDiscard={noop} onCancel={noop} />
  ),
};

const PASTE: PastePlan = {
  rows: 4,
  columns: ["description", "counterparty", "amount"],
  stage: [],
  drafts: [],
  changes: 9,
  refused: [],
  dropped: 0,
  blanks: 0,
  newIdentity: 0,
  needsPreview: true,
};

const paste = (plan: Partial<PastePlan>): StoryObj => ({
  render: () => (
    <PasteDialog
      plan={{ ...PASTE, ...plan }}
      columns={["Description", "Counterparty", "Amount"]}
      singleWrites={plan.newIdentity ?? 0}
      onPaste={noop}
      onCancel={noop}
    />
  ),
});

export const PasteRows = paste({});
export const PasteWithNewIdentity = paste({ newIdentity: 3 });
export const PasteRefusedCells = paste({
  refused: [
    { key: "a", column: "amount", refusal: { key: "required", raw: "" } },
    { key: "b", column: "amount", refusal: { key: "locked", raw: "12" } },
  ],
  dropped: 2,
  blanks: 1,
});
export const PasteNothingChanges = paste({ changes: 0, blanks: 4 });
