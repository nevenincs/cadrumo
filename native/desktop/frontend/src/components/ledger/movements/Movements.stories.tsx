import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { expect, fn, userEvent, waitFor } from "storybook/test";
import { STORY_PERIOD, useLedgerPort, useLedgerRead } from "@/dev/LedgerStage";
import type { Readiness } from "../../../shell/ledgerWindow";
import { parsePercent } from "../../../shell/ledgerGrammar";
import { useStrings } from "../../../shell/strings";
import { pointsText } from "../editing/editingModel";
import { periodText } from "../ledgerWords";
import { ClassifyDialog } from "./ClassifyDialog";
import { ColumnChooser } from "./ColumnChooser";
import {
  DEFAULT_SORT,
  NO_FILTERS,
  columnLayout,
  readinessSets,
  viewFilters,
  type ColumnId,
  type GroupingId,
  type MovementFilters,
  type MovementSort,
  type SavedViewId,
} from "./movementsModel";
import { MovementsToolbar } from "./MovementsToolbar";
import { ReadinessStrip } from "./ReadinessStrip";

// The parts of the Movements section that stand on their own: the readiness
// strip over the readiness the ledger answers to its own check, the toolbar,
// the column chooser and the classify dialog. The grid and the section that
// wires them together are in the page's stories.

const noop = () => undefined;

type StripArgs = {
  readiness?: "checked" | "not_checked" | "checking";
  filters?: Partial<MovementFilters>;
  duplicates?: number;
  unsaved?: number;
  locale: string;
};

function Strip({
  readiness: want = "checked",
  filters,
  duplicates,
  unsaved = 0,
  locale,
}: StripArgs) {
  const t = useStrings();
  const port = useLedgerPort();
  const read = useLedgerRead(port);
  const [chosen, setChosen] = useState<Partial<MovementFilters>>(filters ?? {});
  const readiness: Readiness =
    want === "not_checked"
      ? { kind: "not_checked" }
      : want === "checking"
        ? { kind: "checking", held: null }
        : read.readiness;
  const sets =
    want === "checked" ? read.sets : readinessSets(read.rows ?? [], null);
  return (
    <ReadinessStrip
      readiness={readiness}
      sets={sets}
      filters={{ ...NO_FILTERS, ...chosen }}
      locale={locale}
      unsaved={unsaved}
      stagedClassify={0}
      periodName={periodText(t, locale, STORY_PERIOD)}
      onCheck={read.recheck}
      onPill={(filter) => setChosen({ readiness: filter })}
      onReason={(reason) => setChosen({ reason })}
      duplicates={duplicates}
      onDuplicates={noop}
    />
  );
}

const meta: Meta<typeof Strip> = {
  title: "Ledger/Movements",
  component: Strip,
  render: (args, { globals }) => (
    <Strip {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<typeof Strip>;

export const ReadinessChecked: Story = {
  name: "Readiness strip",
};
export const ReadinessFiltered: Story = {
  name: "Readiness strip, filtering to what needs fixing",
  args: { filters: { readiness: "issues" } },
};
export const ReadinessNotChecked: Story = {
  name: "Readiness strip, not checked",
  args: { readiness: "not_checked" },
};
export const ReadinessChecking: Story = {
  name: "Readiness strip, checking",
  args: { readiness: "checking" },
};
export const ReadinessUnsaved: Story = {
  name: "Readiness strip, with unsaved changes and duplicates",
  args: { unsaved: 3, duplicates: 2 },
};

type ToolbarArgs = { view?: SavedViewId; grouped?: boolean };

function Toolbar({ view, grouped }: ToolbarArgs) {
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<MovementFilters>(
    view ? viewFilters(view) : NO_FILTERS,
  );
  const [saved, setSaved] = useState<SavedViewId | null>(view ?? null);
  const [groupBy, setGroupBy] = useState<GroupingId | null>(
    grouped ? "counterparty" : null,
  );
  const [sort, setSort] = useState<MovementSort>(DEFAULT_SORT);
  const [layout, setLayout] = useState(() =>
    columnLayout({ hidden: [], order: [] }),
  );
  const [density, setDensity] = useState<"compact" | "comfortable">("compact");
  return (
    <div className="p-3">
      <MovementsToolbar
        search={search}
        onSearch={setSearch}
        onLeaveSearch={noop}
        filters={filters}
        onFilters={(next) => {
          setFilters(next);
          setSaved(null);
        }}
        savedView={saved}
        onChooseView={(choice) => {
          setSaved(choice);
          setFilters(viewFilters(choice));
        }}
        groupBy={groupBy}
        onGroupBy={setGroupBy}
        groupAllowed={() => true}
        onFoldAll={noop}
        sort={sort}
        onSort={setSort}
        sortAllowed={() => true}
        layout={layout}
        onLayout={(order: ColumnId[], hidden: ColumnId[]) =>
          setLayout({ order, hidden: new Set(hidden) })
        }
        density={density}
        onDensity={setDensity}
        accounts={[
          { id: "main", label: "Main account" },
          { id: "card", label: "Card account" },
        ]}
        onWantAccounts={noop}
        groupLabels={["Studio", "Home office"]}
        reasons={["missing_category", "missing_proportionality_reference"]}
        status="40 movements"
      />
    </div>
  );
}

export const ToolbarAtRest: StoryObj<ToolbarArgs> = {
  name: "Toolbar",
  render: (args) => <Toolbar {...args} />,
};
export const ToolbarWithView: StoryObj<ToolbarArgs> = {
  name: "Toolbar, a saved view and a grouping",
  args: { view: "to_classify", grouped: true },
  render: (args) => <Toolbar {...args} />,
};

function Columns() {
  const [layout, setLayout] = useState(() =>
    columnLayout({ hidden: [], order: [] }),
  );
  return (
    <div className="flex justify-end p-3">
      <ColumnChooser
        layout={layout}
        onLayout={(order, hidden) =>
          setLayout({ order, hidden: new Set(hidden) })
        }
      />
    </div>
  );
}

export const ColumnsClosed: StoryObj = {
  name: "Column chooser",
  render: () => <Columns />,
};
export const ColumnsOpen: StoryObj = {
  name: "Column chooser, open",
  render: () => <Columns />,
  play: async ({ canvasElement }) => {
    const trigger = await waitFor(() => {
      const found = canvasElement.querySelector<HTMLElement>("button");
      if (!found) throw new Error("the chooser is not drawn yet");
      return found;
    });
    await userEvent.click(trigger);
  },
};

type ClassifyArgs = Partial<Parameters<typeof ClassifyDialog>[0]>;

function Classify(args: ClassifyArgs) {
  return (
    <ClassifyDialog
      kind="business"
      movements={6}
      split={{ expenses: 6, income: 0 }}
      skipped={0}
      partial={false}
      error={null}
      onStage={noop}
      onCancel={noop}
      {...args}
    />
  );
}

const classify = (args: ClassifyArgs): StoryObj => ({
  render: () => <Classify {...args} />,
});

export const ClassifyBusiness = classify({});
export const ClassifyBusinessWithIncome = classify({
  movements: 8,
  split: { expenses: 6, income: 2 },
});
export const ClassifyMixed = classify({
  kind: "mixed",
  ratioOf: (category) =>
    category === "vehicle_fuel"
      ? { staged: 0, missing: 0, unread: 0 }
      : { staged: 0, missing: 4, unread: 0 },
  onOpenRatios: noop,
});
export const ClassifyMixedShareRefused = classify({
  kind: "mixed",
  initialShare: "140",
  error: "A share is between 0 and 100.",
});
const staged = fn();
// What the share staged as the page reads it: typed points reach the wire as
// the same fraction a grid cell gives them.
const shareTyped = (typed: string, fraction: string): StoryObj => ({
  render: () => (
    <Classify
      kind="mixed"
      movements={3}
      split={{ expenses: 0, income: 3 }}
      onStage={staged}
    />
  ),
  play: async () => {
    staged.mockClear();
    const share = await waitFor(() => {
      const found = document.body.querySelector<HTMLInputElement>(
        ".ledger-classify input",
      );
      if (!found) throw new Error("the share is not drawn yet");
      return found;
    });
    await userEvent.type(share, typed);
    await userEvent.click(
      document.body.querySelector<HTMLElement>(".ledger-classify-stage")!,
    );
    await waitFor(() => expect(staged).toHaveBeenCalledTimes(1));
    const answer = staged.mock.calls[0]![0] as { share: string };
    expect(answer.share).toBe(`${typed}%`);
    expect(parsePercent(answer.share)).toEqual({
      kind: "value",
      value: fraction,
    });
    expect(parsePercent(answer.share)).toEqual(parsePercent(pointsText(typed)));
  },
});
export const ClassifyMixedShareTyped = shareTyped("50", "0.5");
export const ClassifyMixedShareUnderOne = shareTyped("0.5", "0.005");
export const ClassifyPersonal = classify({
  kind: "personal",
  overwritten: 3,
  skipped: 1,
});
export const ClassifyCategory = classify({ kind: "category" });
export const ClassifyPartial = classify({
  skipped: 2,
  partial: true,
  range: { count: 12, onSelect: noop },
});
