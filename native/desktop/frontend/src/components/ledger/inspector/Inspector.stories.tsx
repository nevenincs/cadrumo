import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { userEvent, waitFor } from "storybook/test";
import { SEALED_PERIOD } from "@/dev/fixtures/ledger";
import { typeAsAPerson } from "@/dev/personTyping";
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
import { LedgerSuggestions } from "../suggestions/SuggestionsProvider";
import { SplitDialog } from "./SplitDialog";

// The panel beside the movements grid, over the movements the scenario's
// ledger holds: one movement, several, none, and the queue of movements to
// match. The dialogs it opens for a split and for a lifecycle change or
// removal follow.

const noop = () => undefined;

/** The quarter a finalized declaration cites, and the months of it, which the
 * sealed movements fall in. */
const SEALED_STORY_PERIOD: LedgerPeriod = {
  year: SEALED_PERIOD.filing_year,
  code: SEALED_PERIOD.code,
};
const SEALED_STORY_MONTHS = ["01", "02", "03"].map(
  (month) => `${SEALED_PERIOD.filing_year}-${month}`,
);
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
    <LedgerSuggestions
      port={port}
      reader={STORY_READER}
      rows={read.rows}
      stage={stage.content}
      applied={stage.applied}
      locale={locale}
    >
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
    </LedgerSuggestions>
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
    period: SEALED_STORY_PERIOD,
    selected: storyMovementIds(
      (m) => m.sealed && m.transaction.direction === "OUTGOING",
      1,
      SEALED_STORY_MONTHS,
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
const drawn = <Found extends HTMLElement>(
  root: ParentNode,
  selector: string,
): Promise<Found> =>
  waitFor(
    () => {
      const found = root.querySelector<Found>(selector);
      if (!found) throw new Error(`${selector} is not drawn yet`);
      return found;
    },
    { timeout: 5000 },
  );

/** Opens the rarer tax facts, where the Modelo 210 form and the allocation
 * form are. */
const openTaxFacts = async (root: HTMLElement) => {
  const more = await drawn<HTMLDetailsElement>(root, ".ledger-more-tax");
  more.open = true;
  more.scrollIntoView({ block: "start" });
  return more;
};

/** The control whose label is `label` in `form`, once it is drawn. */
const controlOf = <Control extends HTMLElement>(
  form: HTMLElement,
  label: string,
) =>
  waitFor(
    () => {
      const found = [...form.querySelectorAll("label")].find(
        (candidate) => candidate.textContent?.trim() === label,
      );
      const control = found?.htmlFor
        ? form.querySelector<Control>(`[id="${found.htmlFor}"]`)
        : null;
      if (!control) throw new Error(`${label} is not drawn yet`);
      return control;
    },
    { timeout: 5000 },
  );

/** Types into the field whose label is `label` in `form`, then leaves it. */
const typedInto = async (form: HTMLElement, label: string, text: string) =>
  typeAsAPerson(await controlOf<HTMLInputElement>(form, label), text);

/** Opens the list whose label is `label` in `form` and chooses the entry the
 * served list words with `code`. */
const chosenInto = async (form: HTMLElement, label: string, code: string) => {
  await userEvent.click(await controlOf(form, label));
  const entries = await waitFor(
    () => {
      const found = [...document.body.querySelectorAll('[role="option"]')];
      if (found.length === 0) throw new Error("the list is not drawn yet");
      return found;
    },
    { timeout: 5000 },
  );
  const entry = entries.find((found) =>
    found.textContent?.trim().startsWith(code),
  );
  if (!entry) throw new Error(`the list offers nothing for ${code}`);
  await userEvent.click(entry);
};

export const IncomeForNonResident: Story = {
  name: "An incoming movement: the Modelo 210 income form",
  args: {
    selected: storyMovementIds(
      (m) => m.transaction.direction === "INCOMING",
      1,
    ),
  },
  play: async ({ canvasElement }) => {
    const more = await openTaxFacts(canvasElement);
    const form = await drawn<HTMLFormElement>(more, "form");
    const labels = [...form.querySelectorAll("label")].map(
      (label) => label.textContent?.trim() ?? "",
    );
    await chosenInto(form, labels[0]!, "02");
    await typedInto(form, labels[1]!, "12500.5");
    await typedInto(form, labels[4]!, "b12 345 678");
  },
};

export const AllocateShare: Story = {
  name: "A business movement: allocate a share",
  args: {
    selected: storyMovementIds(
      (m) =>
        m.transaction.business_classification === "BUSINESS" &&
        m.transaction.direction === "OUTGOING",
      1,
    ),
  },
  play: async ({ canvasElement }) => {
    const more = await openTaxFacts(canvasElement);
    const forms = await waitFor(
      () => {
        const found = more.querySelectorAll<HTMLFormElement>("form");
        if (found.length < 2) throw new Error("the forms are not drawn yet");
        return found;
      },
      { timeout: 5000 },
    );
    const form = forms[1]!;
    const labels = [...form.querySelectorAll("label")].map(
      (label) => label.textContent?.trim() ?? "",
    );
    await typedInto(form, labels[0]!, "35");
  },
};

export const DeriveIva: Story = {
  name: "A business movement: work out its IVA from a category",
  args: {
    selected: storyMovementIds(
      (m) =>
        m.transaction.business_classification === "BUSINESS" &&
        m.transaction.direction === "OUTGOING",
      1,
    ),
  },
  play: async ({ canvasElement }) => {
    const choose = await drawn<HTMLButtonElement>(
      canvasElement,
      '[data-field="iva-derive"]',
    );
    choose.scrollIntoView({ block: "center" });
    await userEvent.click(choose);
    const option = await drawn<HTMLElement>(document.body, '[role="option"]');
    await userEvent.click(option);
  },
};

export const AttachDocument: Story = {
  name: "A business purchase: attach a document already read",
  args: {
    selected: storyMovementIds(
      (m) =>
        m.transaction.business_classification === "BUSINESS" &&
        m.transaction.direction === "OUTGOING" &&
        m.transaction.purchase_invoice_evidence_id === null,
      1,
    ),
  },
  play: async ({ canvasElement }) => {
    const attach = await drawn<HTMLButtonElement>(
      canvasElement,
      '[data-section-body="documents"] button[aria-haspopup]',
    );
    attach.scrollIntoView({ block: "center" });
    await userEvent.click(attach);
    await drawn<HTMLElement>(document.body, '[role="option"]');
  },
};

export const ToMatch: Story = {
  name: "The queue of movements to match",
  args: { mode: "match" },
};

type SplitArgs = { id?: string; locale: string };

function Split({ id, locale }: SplitArgs) {
  const port = useLedgerPort();
  const read = useLedgerRead(port);
  const row: LedgerRow | undefined =
    read.rows?.find((found) => found.transaction.transaction_id === id) ??
    read.rows?.find(
      (found) => found.transaction.business_classification === "BUSINESS",
    );
  return row ? (
    <SplitDialog
      port={port}
      row={row}
      locale={locale}
      onStage={noop}
      onClose={noop}
      say={noop}
    />
  ) : null;
}

export const SplitMovement: StoryObj<SplitArgs> = {
  name: "Split a movement",
  render: (args, { globals }) => (
    <Split {...args} locale={String(globals.locale ?? "en")} />
  ),
};

export const SplitBusinessPartAdvised: StoryObj<SplitArgs> = {
  name: "Split a movement: a Business part is advised to name a category",
  render: (args, { globals }) => (
    <Split {...args} locale={String(globals.locale ?? "en")} />
  ),
  play: async () => {
    const part = await drawn<HTMLElement>(document.body, ".ledger-split-part");
    await userEvent.selectOptions(part.querySelector("select")!, "BUSINESS");
    await drawn<HTMLElement>(part, ".ledger-split-category-advice");
  },
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
      SEALED_STORY_MONTHS,
    ),
    SEALED_STORY_PERIOD,
  ),
};
export const ActionMerge: StoryObj<ActionArgs> = {
  name: "Merge movements",
  ...action((ids) => ({ kind: "merge", ids })),
};
