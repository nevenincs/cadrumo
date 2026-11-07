import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { userEvent, waitFor, within } from "storybook/test";
import { STORY_PERIOD, STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import { fixtureLedger } from "@/dev/fixtures/ledger";
import { typeAsAPerson } from "@/dev/personTyping";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import { translator } from "../../../shell/strings";
import { usePagePause, WritePauseContext } from "../WritePause";
import { type EditorTarget } from "./InvoiceEditor";
import { InvoicesSection } from "./InvoicesSection";
import { fixtureDay } from "@/dev/fixtureDates";

// The Invoices section of the Ledger page over the scenario's catalogue of
// issued and received invoices, and the editor that adds or corrects one.

const noop = () => undefined;
const NO_LINK = { ask: null, done: noop };

type Args = {
  shape?: LedgerShape;
  period?: LedgerPeriod | null;
  editor?: EditorTarget | null;
  locale: string;
};

function Invoices({ shape, period = STORY_PERIOD, editor, locale }: Args) {
  const port = useLedgerPort(shape);
  const [shown, setShown] = useState<LedgerPeriod | null>(period);
  const [open, setOpen] = useState<EditorTarget | null>(editor ?? null);
  const pause = usePagePause({ reader: STORY_READER, afterReread: noop });
  return (
    <WritePauseContext.Provider value={pause}>
      <div className="flex h-full min-h-0 flex-col">
        <InvoicesSection
          port={port}
          reader={STORY_READER}
          locale={locale}
          period={shown}
          shown
          editor={open}
          onEditor={setOpen}
          copy={async () => undefined}
          onPeriod={setShown}
          linked={NO_LINK}
        />
      </div>
    </WritePauseContext.Provider>
  );
}

const meta: Meta<Args> = {
  title: "Ledger/Invoices",
  render: (args, { globals }) => (
    <Invoices {...args} locale={String(globals.locale ?? "en")} />
  ),
  args: { locale: "en" },
  argTypes: { locale: { table: { disable: true } } },
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj<Args>;

const invoices = fixtureLedger().invoices;
const inQuarter = (kind: "issued" | "received") =>
  invoices.find(
    (invoice) =>
      invoice.kind === kind &&
      invoice.issued_at >= fixtureDay(10, 1) &&
      invoice.issued_at <= fixtureDay(12, 31),
  );

export const Catalogue: Story = {};
export const EveryPeriod: Story = {
  name: "Every period",
  args: { period: null },
};
export const Empty: Story = { args: { shape: "empty" } };
export const Reading: Story = { args: { shape: "slow" } };
export const Unavailable: Story = { args: { shape: "unavailable" } };
export const Large: Story = { args: { shape: "large" } };

export const NewInvoice: Story = {
  name: "Add an invoice",
  args: { editor: { kind: "new" } },
};
export const IssuedInvoice: Story = {
  name: "An issued invoice open",
  args: {
    editor: {
      kind: "open",
      invoiceId: inQuarter("issued")?.invoice_id ?? "",
    },
  },
};
export const ReceivedInvoice: Story = {
  name: "A received invoice open",
  args: {
    editor: {
      kind: "open",
      invoiceId: inQuarter("received")?.invoice_id ?? "",
    },
  },
};

/** The open editor, once it is drawn: it opens beside the page, outside the
 * canvas. */
const editorOf = (canvasElement: HTMLElement) =>
  waitFor(() => {
    const found = canvasElement.ownerDocument.querySelector<HTMLElement>(
      ".ledger-invoice-editor",
    );
    if (!found) throw new Error("the editor is not drawn yet");
    return found;
  });

/** Presses the editor's button named by `key`, once it is there to press. */
async function pressIn(editor: HTMLElement, name: string): Promise<void> {
  const button = await waitFor(() => {
    const found = within(editor).getByRole("button", { name });
    if (found.getAttribute("aria-disabled") === "true")
      throw new Error(`${name} is not ready yet`);
    return found;
  });
  await userEvent.click(button);
}

/** Corrects a stored invoice's notes and saves it, as a person does, so the
 * ledger's answer to the write shows. */
const corrected: NonNullable<Story["play"]> = async ({
  canvasElement,
  globals,
}) => {
  const t = translator(String(globals.locale ?? "en"));
  const cell = await waitFor(() => {
    const found = canvasElement.querySelector<HTMLElement>(
      "[role=row][data-kind=data] [role=gridcell]",
    );
    if (!found) throw new Error("the catalogue is not drawn yet");
    return found;
  });
  await userEvent.dblClick(cell);
  const editor = await editorOf(canvasElement);
  const notes = within(editor).getByLabelText(
    t("desktop.ledger.invoices.field.notes"),
    { exact: true, selector: "input, textarea" },
  );
  await userEvent.type(notes, "Chased by email");
  await pressIn(
    editor,
    t("desktop.ledger.invoices.review_changes", { count: 1 }),
  );
  await pressIn(editor, t("desktop.ledger.invoices.save"));
};

/** Fills a new issued invoice with its four requirements and a line, then
 * adds it, as a person does. */
const added: NonNullable<Story["play"]> = async ({
  canvasElement,
  globals,
}) => {
  const t = translator(String(globals.locale ?? "en"));
  const editor = await editorOf(canvasElement);
  const typed = (key: string, text: string) =>
    typeAsAPerson(
      within(editor).getByLabelText<HTMLInputElement>(
        t(`desktop.ledger.invoices.field.${key}`),
        { exact: true, selector: "input" },
      ),
      text,
    );
  await userEvent.click(
    within(editor).getByRole("radio", {
      name: t("desktop.ledger.invoices.kind_choice.issued"),
    }),
  );
  await typed("counterparty_name", "Norte Digital S. Coop.");
  await typed("counterparty_tax_id", "B00000281");
  await typed("counterparty_country", "ES");
  await typed("series", "F");
  await typed("invoice_number", "F-2026-021");
  await typed("issued_at", fixtureDay(10, 23));
  await typed("currency", "EUR");
  const cells = editor.querySelectorAll<HTMLElement>(
    ".ledger-invoice-lines tbody tr:first-child td",
  );
  await typeAsAPerson(
    cells[0]!.querySelector<HTMLInputElement>("input")!,
    "Brand design",
  );
  await typeAsAPerson(
    cells[2]!.querySelector<HTMLInputElement>("input")!,
    "550",
  );
  const rates = cells[4]!.querySelector<HTMLSelectElement>("select")!;
  // The rates are the ledger's to offer, once it has answered.
  await waitFor(() => {
    if (!rates.querySelector("option[value=RATE_21]"))
      throw new Error("the ledger has not offered its rates yet");
  });
  await userEvent.selectOptions(rates, "RATE_21");
  await pressIn(editor, t("desktop.ledger.invoices.review"));
  await pressIn(editor, t("desktop.ledger.invoices.add"));
};

export const Refused: Story = {
  name: "Correct an invoice, writes refused",
  args: { shape: "refused" },
  play: corrected,
};
export const NewInvoiceRefused: Story = {
  name: "Add an invoice, writes refused",
  args: { shape: "refused", editor: { kind: "new" } },
  play: added,
};

/** Searches the catalogue, as a person does. */
export const Searching: Story = {
  name: "Searching the catalogue",
  play: async ({ canvasElement }) => {
    const search = await waitFor(() => {
      const found = canvasElement.querySelector<HTMLInputElement>(
        "input.ledger-invoices-search",
      );
      if (!found) throw new Error("the search is not drawn yet");
      return found;
    });
    await userEvent.type(search, "estudio");
  },
};
