import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { userEvent, waitFor } from "storybook/test";
import { STORY_PERIOD, STORY_READER, useLedgerPort } from "@/dev/LedgerStage";
import { fixtureLedger } from "@/dev/fixtures/ledger";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import { usePagePause, WritePauseContext } from "../WritePause";
import { type EditorTarget } from "./InvoiceEditor";
import { InvoicesSection } from "./InvoicesSection";

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
      invoice.issued_at >= "2026-10-01" &&
      invoice.issued_at <= "2026-12-31",
  );

export const Catalogue: Story = {};
export const EveryPeriod: Story = {
  name: "Every period",
  args: { period: null },
};
export const Empty: Story = { args: { shape: "empty" } };
export const Reading: Story = { args: { shape: "slow" } };
export const Unavailable: Story = { args: { shape: "unavailable" } };
export const Refused: Story = { args: { shape: "refused" } };
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
export const NewInvoiceRefused: Story = {
  name: "Add an invoice, writes refused",
  args: { shape: "refused", editor: { kind: "new" } },
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
