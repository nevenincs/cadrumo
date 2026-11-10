import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useRef, useState } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { fixtureLedger, type FixtureMovement } from "@/dev/fixtures/ledger";
import {
  STORY_READER,
  storyMovementIds,
  useLedgerPort,
  useLedgerRead,
} from "@/dev/LedgerStage";
import type { LedgerShape } from "@/dev/ledgerFixture";
import type { LedgerPort, OutputLanguage } from "../../../shell/ledger";
import type { CatalogueInvoice } from "../../../shell/ledgerInvoiceOperations";
import { useOwnAccounts } from "../../../shell/ledgerMovementReads";
import { useStrings } from "../../../shell/strings";
import { useLedgerRead as useDocumentRead } from "../documents/useLedgerRead";
import { usePagePause, WritePauseContext } from "../WritePause";
import { documentOverview } from "./documentOverviewModel";
import { EntryOverview, type OverviewAction } from "./EntryOverview";
import { invoiceOverview } from "./invoiceOverviewModel";
import { MovementOverview } from "./MovementOverview";

// The overview of one ledger entry over the scenario's ledger: a movement in
// each of its classifications and in a foreign currency, an invoice, an
// evidence record and its reading, and the same entries where what the page
// would read is not known. Each opens over a page that only reads; the last
// story opens one, reads it and closes it with Escape.

const noop = () => undefined;

/** The one action, as each section offers it; here it does nothing. */
function useAction(kind: "movement" | "invoice" | "document"): OverviewAction {
  const t = useStrings();
  return kind === "movement"
    ? {
        label: t("desktop.ledger.overview.open_movement"),
        icon: "edit",
        run: noop,
      }
    : kind === "invoice"
      ? {
          label: t("desktop.ledger.inspector.invoice.open"),
          icon: "edit",
          run: noop,
        }
      : {
          label: t("desktop.ledger.overview.open_record"),
          icon: "edit",
          run: noop,
        };
}

/** A port whose movement lineage cannot be read, as when the ledger stops
 * answering after the period was read. */
function withoutLineage(port: LedgerPort): LedgerPort {
  return new Proxy(port, {
    get(target, name, receiver) {
      if (name !== "submit") return Reflect.get(target, name, receiver);
      const submit = target.submit.bind(target);
      return ((definition, request) =>
        definition === "ledger.track"
          ? Promise.reject(new Error("unavailable"))
          : submit(definition, request)) as LedgerPort["submit"];
    },
  });
}

type MovementArgs = {
  pick: (movement: FixtureMovement) => boolean;
  /** Readiness is shown as not measured and the lineage as not read. */
  unknown?: boolean;
  locale: string;
};

function Movement({ pick, unknown = false, locale }: MovementArgs) {
  const fixturePort = useLedgerPort();
  const port = useMemo(
    () => (unknown ? withoutLineage(fixturePort) : fixturePort),
    [fixturePort, unknown],
  );
  const read = useLedgerRead(fixturePort, undefined, locale as OutputLanguage);
  const accounts = useOwnAccounts(fixturePort, STORY_READER, true);
  const action = useAction("movement");
  const [id] = useState(() => storyMovementIds(pick, 1)[0] ?? null);
  const movement = fixtureLedger().movements.find(
    (found) => found.transaction.transaction_id === id,
  );
  const row = read.rows?.find(
    (found) => found.transaction.transaction_id === id,
  );
  if (!row || read.generation === null) return null;
  return (
    <MovementOverview
      port={port}
      row={row}
      generation={read.generation}
      issues={
        unknown || !read.sets.checked ? null : (read.sets.issues.get(id!) ?? [])
      }
      duplicate={movement?.issue === "duplicate"}
      accounts={accounts}
      unsaved={0}
      locale={locale}
      action={action}
      onClose={noop}
    />
  );
}

const movementStory = (
  name: string,
  pick: MovementArgs["pick"],
  unknown = false,
): StoryObj<MovementArgs> => ({
  name,
  args: { pick, unknown },
  render: (args, { globals }) => (
    <Movement {...args} locale={String(globals.locale ?? "en")} />
  ),
});

const outgoing = (movement: FixtureMovement) =>
  movement.transaction.direction === "OUTGOING";

export const MovementBusiness = movementStory(
  "A business movement",
  (m) =>
    outgoing(m) &&
    m.transaction.business_classification === "BUSINESS" &&
    m.transaction.invoice_id !== null,
);
export const MovementMixed = movementStory(
  "A mixed movement",
  (m) => m.transaction.business_classification === "MIXED",
);
export const MovementPersonal = movementStory(
  "A personal movement",
  (m) => outgoing(m) && m.transaction.business_classification === "PERSONAL",
);
export const MovementUnclassified = movementStory(
  "A movement still to classify",
  (m) => m.transaction.business_classification === "NOT_YET_PROCESSED",
);
export const MovementForeign = movementStory(
  "A movement in a foreign currency",
  (m) => m.transaction.currency !== "EUR",
);
export const MovementUnknown = movementStory(
  "A movement: readiness not measured, origin not read",
  (m) => m.transaction.business_classification === "BUSINESS",
  true,
);

type InvoiceArgs = {
  pick: (invoice: CatalogueInvoice) => boolean;
  /** What the overview is given in place of the stored invoice. */
  change?: (invoice: CatalogueInvoice) => CatalogueInvoice;
  locale: string;
};

function Invoice({ pick, change, locale }: InvoiceArgs) {
  const t = useStrings();
  const action = useAction("invoice");
  const found = fixtureLedger().invoices.find(pick);
  if (!found) return null;
  return (
    <EntryOverview
      model={invoiceOverview(t, locale, change ? change(found) : found)}
      action={action}
      onClose={noop}
    />
  );
}

const invoiceStory = (
  name: string,
  pick: InvoiceArgs["pick"],
  change?: InvoiceArgs["change"],
): StoryObj<InvoiceArgs> => ({
  name,
  args: { pick, ...(change ? { change } : {}) },
  render: (args, { globals }) => (
    <Invoice {...args} locale={String(globals.locale ?? "en")} />
  ),
});

export const InvoiceReceived = invoiceStory(
  "A received invoice linked to its payment",
  (invoice) =>
    invoice.kind === "received" && invoice.linked_transaction_ids.length > 0,
);
export const InvoiceIssuedWithRetention = invoiceStory(
  "An issued invoice with a withholding",
  (invoice) => invoice.kind === "issued" && invoice.retention_amount !== null,
);
export const InvoiceForeign = invoiceStory(
  "An invoice in a foreign currency, no EUR rate",
  (invoice) => invoice.currency !== "EUR",
);
export const InvoiceNothingStated = invoiceStory(
  "An invoice that states little",
  (invoice) => invoice.kind === "received",
  (invoice) => ({
    ...invoice,
    counterparty_tax_id: null,
    iva_category: null,
    operation_date: null,
    operation_type: null,
    linked_transaction_ids: [],
    source_filename: null,
    source_row_index: null,
    notes: "",
  }),
);

type DocumentArgs = {
  shape?: LedgerShape;
  /** Which record: one with a reading waiting, or one without. */
  waiting: boolean;
  /** The reading and the movements are shown as not read. */
  unknown?: boolean;
  locale: string;
};

function DocumentBody({ waiting, unknown = false, locale }: DocumentArgs) {
  const t = useStrings();
  const port = useLedgerPort("documents");
  const read = useLedgerRead(port);
  const action = useAction("document");
  const records = useDocumentRead(
    port,
    STORY_READER,
    true,
    "ledger.evidence.list",
    {},
  );
  const queue = useDocumentRead(
    port,
    STORY_READER,
    true,
    "ledger.evidence.review.list",
    {},
  );
  const list = records.read.value?.rows ?? null;
  const rows = queue.read.value?.rows ?? null;
  if (list === null || rows === null || read.rows === null) return null;
  const waitingOn = new Set(rows.map((row) => row.evidence_reference));
  const record = list.find(
    (found) => waitingOn.has(found.evidence_id) === waiting,
  );
  if (!record) return null;
  const row = rows.find(
    (found) => found.evidence_reference === record.evidence_id,
  );
  const attached = read.rows.find(
    (found) =>
      found.transaction.purchase_invoice_evidence_id === record.evidence_id,
  );
  return (
    <EntryOverview
      model={documentOverview({
        t,
        locale,
        record,
        reading: unknown
          ? { kind: "unknown" }
          : row
            ? { kind: "waiting", row }
            : { kind: "none" },
        attachment: unknown
          ? { kind: "unknown" }
          : attached
            ? { kind: "attached", row: attached }
            : { kind: "not_found" },
      })}
      action={action}
      onClose={noop}
    />
  );
}

function Document(args: DocumentArgs) {
  const pause = usePagePause({ reader: STORY_READER, afterReread: noop });
  return (
    <WritePauseContext.Provider value={pause}>
      <DocumentBody {...args} />
    </WritePauseContext.Provider>
  );
}

const documentStory = (
  name: string,
  waiting: boolean,
  unknown = false,
): StoryObj<DocumentArgs> => ({
  name,
  args: { waiting, unknown },
  render: (args, { globals }) => (
    <Document {...args} locale={String(globals.locale ?? "en")} />
  ),
});

export const DocumentInReview = documentStory(
  "A document with a reading waiting for review",
  true,
);
export const DocumentRecorded = documentStory(
  "A document recorded, nothing waiting",
  false,
);
export const DocumentUnknown = documentStory(
  "A document: reading and movement not read",
  false,
  true,
);

/** An opener in a page, as a grid row is: the overview opens from it and
 * gives the focus back to it as it closes. */
function Opener({ locale }: { locale: string }) {
  const t = useStrings();
  const action = useAction("invoice");
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const invoice = fixtureLedger().invoices.find(
    (found) => found.kind === "received",
  );
  return (
    <div className="p-6">
      <Button
        ref={opener}
        variant="outline"
        className="ledger-overview-opener"
        onClick={() => setOpen(true)}
      >
        <Icon name="eye" />
        {t("desktop.ledger.overview.show")}
      </Button>
      {open && invoice && (
        <EntryOverview
          model={invoiceOverview(t, locale, invoice)}
          action={action}
          onClose={() => setOpen(false)}
          onClosed={() => opener.current?.focus()}
        />
      )}
    </div>
  );
}

export const OpenReadAndClose: StoryObj<{ locale: string }> = {
  name: "Open, read, and close with Escape",
  render: (_, { globals }) => (
    <Opener locale={String(globals.locale ?? "en")} />
  ),
  play: async ({ canvasElement }) => {
    const opener = within(canvasElement).getByRole("button");
    await userEvent.click(opener);
    const dialog = await waitFor(() => {
      const found = document.body.querySelector<HTMLElement>(
        '[role="dialog"].ledger-overview',
      );
      if (!found) throw new Error("the overview is not open yet");
      return found;
    });
    // The summary takes the focus itself; the action waits to be chosen.
    await waitFor(() => expect(document.activeElement).toBe(dialog));
    const title = dialog.querySelector(".ledger-overview-title");
    await expect(title?.textContent).toBeTruthy();
    await expect(dialog.getAttribute("aria-labelledby")).toBe(title?.id);
    await expect(
      dialog.querySelector('[data-fact="grand_total"]')?.textContent,
    ).toBeTruthy();
    // The focus stays inside while it is open, forwards and backwards, and
    // reaches both the action and the close button on the way.
    const reached = new Set<Element>();
    for (const keys of ["{Tab}", "{Tab}", "{Tab}", "{Shift>}{Tab}{/Shift}"]) {
      for (let step = 0; step < 3; step += 1) {
        await userEvent.keyboard(keys);
        const focused = document.activeElement;
        await expect(focused && dialog.contains(focused)).toBe(true);
        if (focused) reached.add(focused);
      }
    }
    await expect(
      [...reached].some((found) =>
        found.classList.contains("ledger-overview-action"),
      ),
    ).toBe(true);
    await expect(reached.size).toBeGreaterThan(1);
    await userEvent.keyboard("{Escape}");
    await waitFor(() =>
      expect(
        document.body.querySelector('[role="dialog"].ledger-overview'),
      ).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(opener));
  },
};

const meta: Meta = {
  title: "Ledger/Entry overview",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
