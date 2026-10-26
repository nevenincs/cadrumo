import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { userEvent, waitFor } from "storybook/test";
import { STORY_PERIOD, useLedgerPort, useLedgerRead } from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerExportFormat } from "../../../shell/ledger";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import { translator } from "../../../shell/strings";
import { ExportDialog } from "./ExportDialog";
import { ImportDialog } from "./ImportDialog";
import type { ImportKind } from "./importModel";

// The Import and Export dialogs of the Ledger page over the scenario's
// ledger. The import is walked on through the made-up computer's own files:
// a bank statement, an invoice book, documents. Nothing leaves the
// scenario; the files it offers are synthetic.

const noop = () => undefined;
/** Waits for what a slow machine draws late. */
const WAIT = { timeout: 5000 };
const YEARS = [2025, 2026];

type ExportArgs = {
  shape?: LedgerShape;
  period?: LedgerPeriod | null;
  format?: LedgerExportFormat;
  staged?: number;
  selected?: number;
  locale: string;
};

function Export({
  shape,
  period = STORY_PERIOD,
  format = "csv",
  staged = 0,
  selected = 0,
  locale,
}: ExportArgs) {
  const port = useLedgerPort(shape);
  const read = useLedgerRead(port);
  const [chosen, setChosen] = useState(format);
  return (
    <ExportDialog
      port={port}
      locale={locale}
      period={period}
      years={YEARS}
      fallbackYear={STORY_PERIOD.year}
      format={chosen}
      onFormat={setChosen}
      staged={staged}
      onReviewStaged={noop}
      selection={(read.rows ?? []).slice(0, selected)}
      copy={async () => undefined}
      onClose={noop}
    />
  );
}

const meta: Meta<ExportArgs> = {
  title: "Ledger/Transfer",
  render: (args, { globals }) => (
    <Export {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<ExportArgs>;

export const ExportQuarter: Story = { name: "Export" };
export const ExportEveryPeriod: Story = {
  name: "Export, every period",
  args: { period: null },
};
export const ExportSpreadsheet: Story = {
  name: "Export, as a spreadsheet",
  args: { format: "xlsx" },
};
export const ExportWithStaged: Story = {
  name: "Export, with changes not saved",
  args: { staged: 3 },
};
export const ExportSelection: Story = {
  name: "Export, with movements selected",
  args: { selected: 3 },
};
export const ExportUnavailable: Story = {
  name: "Export, ledger not answering",
  args: { shape: "unavailable" },
};

type ImportArgs = {
  shape?: LedgerShape;
  /** The kind of file to choose, and so the step reached. */
  kind?: ImportKind;
  locale: string;
};

function Import({ shape, locale }: ImportArgs) {
  const port = useLedgerPort(shape);
  return (
    <ImportDialog
      port={port}
      locale={locale}
      period={STORY_PERIOD}
      years={YEARS}
      fallbackYear={STORY_PERIOD.year}
      onClose={noop}
      onWritten={noop}
      onShowImported={noop}
      onShowDocuments={noop}
    />
  );
}

/** Walks the dialog to choosing files of `kind`, as a person does. */
const choosing =
  (kind: ImportKind = "bank"): NonNullable<StoryObj<ImportArgs>["play"]> =>
  async ({ canvasElement, globals }) => {
    const t = translator(String(globals.locale ?? "en"));
    const body = canvasElement.ownerDocument.body;
    const named = (name: string, role: string) =>
      waitFor(() => {
        const found = [
          ...body.querySelectorAll<HTMLElement>(`[role=${role}]`),
        ].find((element) => element.textContent?.includes(name));
        if (!found) throw new Error(`${name} is not drawn yet`);
        return found;
      }, WAIT);
    if (kind !== "bank")
      await userEvent.click(
        await named(t(`desktop.ledger.import.kind.${kind}`), "radio"),
      );
    const choose = await waitFor(() => {
      const found = [...body.querySelectorAll<HTMLElement>("button")].find(
        (button) =>
          button.textContent?.includes(
            t(
              kind === "book"
                ? "desktop.ledger.import.choose_file"
                : "desktop.ledger.import.choose_files",
            ),
          ),
      );
      if (!found) throw new Error("the file button is not drawn yet");
      return found;
    }, WAIT);
    await userEvent.click(choose);
  };

const importing = (
  args: Partial<ImportArgs>,
  play?: StoryObj<ImportArgs>["play"],
  name?: string,
): StoryObj<ImportArgs> => ({
  name,
  args,
  play,
  render: (props, { globals }) => (
    <Import {...props} locale={String(globals.locale ?? "en")} />
  ),
});

export const ImportWhat = importing({}, undefined, "Import");
export const ImportStatements = importing(
  {},
  choosing(),
  "Import, bank statements chosen",
);
export const ImportInvoiceBook = importing(
  {},
  choosing("book"),
  "Import, an invoice book chosen",
);
export const ImportDocuments = importing(
  {},
  choosing("documents"),
  "Import, documents chosen",
);
export const ImportUnavailable = importing(
  { shape: "unavailable" },
  choosing(),
  "Import, ledger not answering",
);
