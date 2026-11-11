import settings from "virtual:operational-settings";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { DataGrid } from "@/components/ui/data-grid";
import { DataGridText } from "@/components/ui/data-grid-text";
import {
  type DataGridHandle,
  type GridColumn,
  type GridRow,
} from "@/components/ui/dataGridTypes";
import { EmptyState } from "@/components/ui/empty";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { Toast } from "@/components/ui/toast";
import type { CatalogueInvoice } from "../../../shell/ledgerInvoiceOperations";
import type { LedgerPort } from "../../../shell/ledger";
import type { LedgerPeriod } from "../../../shell/ledgerGrammar";
import { useFocusTarget } from "../../../shell/navigation/hooks";
import { useStrings, type Translate } from "../../../shell/strings";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount } from "../../../shared/numbers";
import { RowRevealNotice, useRowReveal, type LinkedRow } from "../RowReveal";
import { PAYMENT_STATUSES } from "../../../shell/ledgerContract";
import { periodBounds, usePeriods } from "../../../shell/ledgerPeriods";
import { ServedOptions } from "../suggestions/ServedOptions";
import { useVocabulary } from "../suggestions/SuggestionsProvider";
import { INVOICE_TSV_COLUMNS, invoicesTsv } from "../transfer/tsv";
import { InvoiceEditor, type EditorTarget } from "./InvoiceEditor";
import {
  filterCatalogue,
  seriesAndNumber,
  sortCatalogue,
  type CatalogueFilter,
  type CatalogueSort,
  type CatalogueSortKey,
} from "./invoiceModel";
import { classLabel, kindLabel, paymentLabel } from "./invoiceWords";
import { invoiceHiding, withoutHiding } from "./invoiceReveal";
import { useInvoiceCatalogue } from "./useInvoiceCatalogue";
import { chordMatches } from "@/shared/chords";
import { ContextMenu, type MenuAnchor } from "../../ContextMenu";
import { typing } from "../overview/overviewKeys";
import { OVERVIEW_CHORD, OVERVIEW_CHORDS } from "../ledgerChords";
import { EntryOverview } from "../overview/EntryOverview";
import { invoiceOverview } from "../overview/invoiceOverviewModel";

const KINDS = ["all", "issued", "received"] as const;

type Column = {
  id: CatalogueSortKey;
  width: number;
  grow?: number;
  minWidth?: number;
  sticky?: "start" | "end";
  align?: "end";
  cell: (invoice: CatalogueInvoice) => ReactNode;
};

const quiet = (text: string) => (
  <DataGridText className="text-muted-foreground">{text}</DataGridText>
);
const amount = (locale: string, value: { decimal: string } | null) =>
  value === null ? null : (
    <span className="tabular-nums">{formatAmount(locale, value.decimal)}</span>
  );

function catalogueColumns(t: Translate, locale: string): Column[] {
  return [
    {
      id: "number",
      width: 9,
      sticky: "start",
      cell: (invoice) => (
        <DataGridText className="ledger-invoice-number font-medium">
          {seriesAndNumber(invoice)}
        </DataGridText>
      ),
    },
    {
      id: "kind",
      width: 6,
      cell: (invoice) => (
        <DataGridText>{kindLabel(t, invoice.kind)}</DataGridText>
      ),
    },
    {
      id: "date",
      width: 7,
      cell: (invoice) => (
        <span className="tabular-nums">
          {formatDay(locale, invoice.issued_at)}
        </span>
      ),
    },
    {
      id: "operation_date",
      width: 7,
      cell: (invoice) =>
        invoice.operation_date &&
        invoice.operation_date !== invoice.issued_at ? (
          <span className="tabular-nums">
            {formatDay(locale, invoice.operation_date)}
          </span>
        ) : null,
    },
    {
      id: "counterparty",
      width: 12,
      grow: 1,
      minWidth: 10,
      cell: (invoice) => (
        <DataGridText>{invoice.counterparty_name}</DataGridText>
      ),
    },
    {
      id: "tax_id",
      width: 8,
      cell: (invoice) =>
        invoice.counterparty_tax_id ? (
          <DataGridText className="font-mono text-sm">
            {invoice.counterparty_tax_id}
          </DataGridText>
        ) : (
          quiet(t("desktop.ledger.invoices.none"))
        ),
    },
    {
      id: "country",
      width: 4,
      cell: (invoice) => <span>{invoice.counterparty_country}</span>,
    },
    {
      id: "class",
      width: 8,
      cell: (invoice) => (
        <DataGridText>{classLabel(t, invoice.invoice_class)}</DataGridText>
      ),
    },
    {
      id: "base",
      width: 7,
      align: "end",
      cell: (invoice) => amount(locale, invoice.base_total),
    },
    {
      id: "iva",
      width: 6,
      align: "end",
      cell: (invoice) => amount(locale, invoice.iva_total),
    },
    {
      id: "recargo",
      width: 6,
      align: "end",
      cell: (invoice) => amount(locale, invoice.recargo_amount),
    },
    {
      id: "retention",
      width: 6.5,
      align: "end",
      cell: (invoice) => amount(locale, invoice.retention_amount),
    },
    {
      id: "total",
      width: 7.5,
      // As a movement's amount does, the total stays in view.
      sticky: "end",
      align: "end",
      cell: (invoice) => (
        <span className="font-medium tabular-nums">
          {formatAmount(locale, invoice.grand_total.decimal)}
        </span>
      ),
    },
    {
      id: "currency",
      width: 4.5,
      cell: (invoice) => <span>{invoice.currency}</span>,
    },
    {
      id: "linked",
      width: 6,
      cell: (invoice) => {
        const count = invoice.linked_transaction_ids.length;
        return count > 0 ? (
          <span
            className="inline-flex items-center gap-1 tabular-nums"
            aria-label={t("desktop.ledger.invoices.linked_count", { count })}
          >
            <Icon name="link" size="xs" />
            {count}
          </span>
        ) : (
          quiet(t("desktop.ledger.invoices.unmatched"))
        );
      },
    },
    {
      id: "payment",
      width: 7.5,
      cell: (invoice) => (
        <span className="inline-flex min-w-0 items-center gap-1">
          {invoice.payment_status === "OVERDUE" && (
            <Icon name="alert" size="xs" className="shrink-0 text-warning" />
          )}
          <DataGridText>{paymentLabel(t, invoice.payment_status)}</DataGridText>
        </span>
      ),
    },
    {
      id: "notes",
      width: 10,
      cell: (invoice) =>
        invoice.notes ? <DataGridText>{invoice.notes}</DataGridText> : null,
    },
  ];
}

/**
 * The Invoices section: the whole catalogue, issued and received, filtered
 * and sorted here because the ledger lists it by kind only, and the editor
 * a row or the page's Add opens. Rows show what is stored.
 */
export function InvoicesSection({
  port,
  reader,
  locale,
  period,
  shown,
  editor,
  onEditor,
  copy,
  onPeriod,
  linked,
}: {
  port: LedgerPort;
  reader: string | null;
  locale: string;
  period: LedgerPeriod | null;
  shown: boolean;
  editor: EditorTarget | null;
  onEditor(target: EditorTarget | null): void;
  copy(text: string): Promise<void>;
  /** Shows another period, to show an invoice the period shown hides. */
  onPeriod?: (period: LedgerPeriod | null) => void;
  /** The invoice a link selects, held by the page. */
  linked: LinkedRow;
}) {
  const t = useStrings();
  const vocabulary = useVocabulary();
  const { read, reread, settle } = useInvoiceCatalogue(port, reader, shown);
  const [filter, setFilter] = useState<Omit<CatalogueFilter, "period">>({
    kind: "all",
    search: "",
    invoiceClass: "",
    payment: "",
    unmatched: false,
  });
  const [sort, setSort] = useState<CatalogueSort>({
    key: "date",
    direction: "desc",
  });
  const [toast, setToast] = useState<string | null>(null);
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(
      () => setToast(null),
      settings.ledger_toast_ms,
    );
    return () => window.clearTimeout(timer);
  }, [toast]);

  const invoices = read.invoices;
  // The period's days are the backend's; until they are served the period
  // keeps no invoice, and the grid is not drawn as if it held none.
  usePeriods({ years: period ? [period.year] : [] });
  const periodUnknown = period !== null && periodBounds(period) === null;
  const rows = useMemo(
    () =>
      invoices === null || periodUnknown
        ? []
        : sortCatalogue(filterCatalogue(invoices, { ...filter, period }), sort),
    [invoices, periodUnknown, filter, period, sort],
  );
  const columns = useMemo<GridColumn<CatalogueInvoice>[]>(
    () =>
      catalogueColumns(t, locale).map((column) => ({
        id: column.id,
        header: t(`desktop.ledger.invoices.column.${column.id}`),
        width: column.width,
        ...(column.grow !== undefined ? { grow: column.grow } : {}),
        ...(column.minWidth !== undefined ? { minWidth: column.minWidth } : {}),
        ...(column.sticky ? { sticky: column.sticky } : {}),
        ...(column.align ? { align: column.align } : {}),
        sortable: true,
        resizable: true,
        cell: column.cell,
      })),
    [t, locale],
  );
  const gridRows = useMemo<GridRow<CatalogueInvoice>[]>(
    () =>
      rows.map((invoice) => ({
        kind: "data",
        key: invoice.invoice_id,
        data: invoice,
      })),
    [rows],
  );
  // A link that selects an invoice reveals it once the grid draws it; one
  // the person's own view hides is announced with what shows it.
  const grid = useRef<DataGridHandle>(null);
  const within = useRef<HTMLDivElement>(null);
  useFocusTarget(
    "ledger/invoices",
    () =>
      within.current?.querySelector<HTMLElement>(
        '[role="grid"] [tabindex="0"]',
      ) ?? null,
  );
  const reveal = useRowReveal(linked, {
    shown: (id) => rows.some((invoice) => invoice.invoice_id === id),
    hiding: (id) => {
      const invoice = invoices?.find((found) => found.invoice_id === id);
      const hiding = invoice ? invoiceHiding(invoice, filter, period) : null;
      if (!hiding || (hiding.period && !onPeriod)) return null;
      return () => {
        setFilter((held) => withoutHiding(held, hiding));
        if (hiding.period) onPeriod?.(null);
      };
    },
    // A catalogue that could not be read draws no grid: the invoice is not
    // here either way.
    settled: (invoices !== null && !periodUnknown) || read.phase === "failed",
    reveal: (id, focus) => {
      if (focus) grid.current?.focusCell(id);
      else grid.current?.scrollToKey(id, "center");
    },
    drawn: rows,
    within,
  });
  // An invoice's overview, and the cell it was asked from, which takes the
  // focus back as it closes unless the overview opened the editor.
  const [overview, setOverview] = useState<{
    key: string;
    column: string;
  } | null>(null);
  const [menu, setMenu] = useState<{ key: string; at: MenuAnchor } | null>(
    null,
  );
  const overviewInvoice = overview
    ? invoices?.find((found) => found.invoice_id === overview.key)
    : undefined;
  const openOverview = (key: string) =>
    setOverview({
      key,
      column: grid.current?.activeCell()?.column ?? "number",
    });
  const set = <K extends keyof typeof filter>(
    key: K,
    value: (typeof filter)[K],
  ) => setFilter((held) => ({ ...held, [key]: value }));
  const filtered =
    filter.kind !== "all" ||
    filter.search.trim() !== "" ||
    filter.invoiceClass !== "" ||
    filter.payment !== "" ||
    filter.unmatched;

  let body: ReactNode;
  if (read.phase === "failed")
    body = (
      <EmptyState
        className="ledger-invoices-failed"
        icon="alert"
        description={
          <span role="alert">{t("desktop.ledger.invoices.read_failed")}</span>
        }
      >
        <Button variant="outline" onClick={reread}>
          {t("desktop.ledger.retry")}
        </Button>
      </EmptyState>
    );
  else if (invoices === null || periodUnknown)
    body = (
      <EmptyState
        className="ledger-invoices-loading"
        role="status"
        busy
        description={t("desktop.ledger.loading")}
      />
    );
  else
    body = (
      <DataGrid
        ref={grid}
        className="ledger-invoices-grid rounded-md"
        label={t("desktop.ledger.invoices.grid")}
        columns={columns}
        moreColumnsLabel={(count) =>
          t("desktop.ledger.columns.more_name", { count })
        }
        earlierColumnsLabel={(count) =>
          t("desktop.ledger.columns.earlier_name", { count })
        }
        rows={gridRows}
        positionLabel={(row, count) =>
          t("desktop.ledger.position", { row, count })
        }
        sort={{ column: sort.key, direction: sort.direction }}
        onSort={(column) =>
          setSort((held) =>
            held.key === column
              ? {
                  key: held.key,
                  direction: held.direction === "asc" ? "desc" : "asc",
                }
              : { key: column as CatalogueSortKey, direction: "asc" },
          )
        }
        onActivate={(key) => onEditor({ kind: "open", invoiceId: key })}
        onMenu={(key, _column, at) => setMenu({ key, at })}
        rowState={(key) =>
          editor?.kind === "open" && editor.invoiceId === key
            ? { current: true }
            : undefined
        }
        empty={
          <EmptyState
            className="ledger-invoices-empty"
            icon="page"
            description={t(
              filtered || period !== null
                ? "desktop.ledger.invoices.empty_filtered"
                : "desktop.ledger.invoices.empty",
            )}
          />
        }
      />
    );

  return (
    <div
      ref={within}
      className="ledger-invoices flex min-h-0 flex-1 flex-col gap-2 p-3"
      onKeyDown={(event) => {
        if (
          event.defaultPrevented ||
          !OVERVIEW_CHORDS.some((chord) => chordMatches(chord, event))
        )
          return;
        const key = grid.current?.activeCell()?.key;
        if (
          !key ||
          typing(event.target) ||
          !invoices?.some((found) => found.invoice_id === key)
        )
          return;
        event.preventDefault();
        openOverview(key);
      }}
    >
      <div
        role="group"
        aria-label={t("desktop.ledger.invoices.toolbar")}
        className="ledger-invoices-toolbar flex flex-wrap items-center gap-2"
      >
        <SegmentedControl
          aria-label={t("desktop.ledger.invoices.kind_filter")}
          value={filter.kind}
          onValueChange={(value) =>
            set("kind", value as CatalogueFilter["kind"])
          }
          className="ledger-invoices-kind"
        >
          {KINDS.map((kind) => (
            <SegmentedControlItem key={kind} value={kind} className="text-sm">
              {t(`desktop.ledger.invoices.kinds.${kind}`)}
            </SegmentedControlItem>
          ))}
        </SegmentedControl>
        <div className="relative w-56 max-w-full">
          <Icon
            name="search"
            size="xs"
            className="pointer-events-none absolute top-1/2 left-2 -translate-y-1/2 text-faint"
          />
          <Input
            type="search"
            controlSize="sm"
            className="ledger-invoices-search pl-7"
            maxLength={128}
            aria-label={t("desktop.ledger.invoices.search")}
            placeholder={t("desktop.ledger.invoices.search_placeholder")}
            value={filter.search}
            onChange={(event) => set("search", event.target.value)}
          />
        </div>
        <div className="w-40">
          <NativeSelect
            controlSize="sm"
            className="ledger-invoices-class text-sm"
            aria-label={t("desktop.ledger.invoices.class_filter")}
            value={filter.invoiceClass}
            onChange={(event) => set("invoiceClass", event.target.value)}
          >
            <option value="">{t("desktop.ledger.invoices.any_class")}</option>
            <ServedOptions
              values={vocabulary.invoiceClasses}
              stored={filter.invoiceClass}
              label={(token) => classLabel(t, token)}
            />
          </NativeSelect>
        </div>
        <div className="w-40">
          <NativeSelect
            controlSize="sm"
            className="ledger-invoices-payment text-sm"
            aria-label={t("desktop.ledger.invoices.payment_filter")}
            value={filter.payment}
            onChange={(event) => set("payment", event.target.value)}
          >
            <option value="">{t("desktop.ledger.invoices.any_payment")}</option>
            {PAYMENT_STATUSES.map((status) => (
              <option key={status} value={status}>
                {paymentLabel(t, status)}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button
          variant="pill"
          size="xs"
          className="ledger-invoices-unmatched"
          aria-pressed={filter.unmatched}
          onClick={() => set("unmatched", !filter.unmatched)}
        >
          {t("desktop.ledger.invoices.unmatched")}
        </Button>
        <span
          className="ledger-invoices-count ml-auto text-sm text-muted-foreground tabular-nums"
          aria-live="polite"
          data-shown={invoices === null ? undefined : rows.length}
          data-total={invoices === null ? undefined : invoices.length}
        >
          {invoices === null
            ? null
            : t("desktop.ledger.invoices.count", {
                shown: rows.length,
                total: invoices.length,
              })}
        </span>
        <IconButton
          label={t("desktop.ledger.export.copy_selection")}
          aria-disabled={rows.length === 0 ? true : undefined}
          onClick={() => {
            if (rows.length === 0) return;
            const header = INVOICE_TSV_COLUMNS.map((column) =>
              t(`desktop.ledger.export.tsv.${column}`),
            );
            copy(invoicesTsv(header, rows)).then(
              () =>
                setToast(
                  t("desktop.ledger.export.copied_invoices", {
                    count: rows.length,
                  }),
                ),
              () => setToast(t("desktop.ledger.export.copy_failed")),
            );
          }}
        >
          <Icon name="copy" />
        </IconButton>
      </div>
      <RowRevealNotice
        {...reveal}
        hidden={t("desktop.ledger.reveal.invoice_hidden")}
        missing={t("desktop.ledger.reveal.invoice_missing")}
      />
      <div className="flex min-h-0 flex-1 flex-col">{body}</div>
      {editor && invoices !== null && (
        <InvoiceEditor
          key={editor.kind === "open" ? editor.invoiceId : "new"}
          port={port}
          locale={locale}
          invoices={invoices}
          target={editor}
          onClose={() => onEditor(null)}
          onWritten={(invoice, removed) => {
            settle(invoice, removed);
            reread();
          }}
          onOpenInvoice={(invoiceId) => onEditor({ kind: "open", invoiceId })}
          say={setToast}
        />
      )}
      {menu && (
        <ContextMenu
          label={t("desktop.ledger.menu")}
          items={[
            {
              id: "overview",
              label: t("desktop.ledger.overview.show"),
              icon: "eye",
              chord: OVERVIEW_CHORD,
              enabled: true,
            },
            {
              id: "open",
              label: t("desktop.ledger.inspector.invoice.open"),
              icon: "edit",
              enabled: true,
            },
          ]}
          at={menu.at}
          choose={(id) => {
            const key = menu.key;
            setMenu(null);
            if (id === "open") onEditor({ kind: "open", invoiceId: key });
            else if (id === "overview")
              // Opened once the menu has handed the focus back to the grid.
              window.requestAnimationFrame(() => openOverview(key));
          }}
        />
      )}
      {overview && overviewInvoice && (
        <EntryOverview
          model={invoiceOverview(t, locale, overviewInvoice)}
          action={{
            label: t("desktop.ledger.inspector.invoice.open"),
            icon: "edit",
            run: () => onEditor({ kind: "open", invoiceId: overview.key }),
          }}
          onClose={() => setOverview(null)}
          onClosed={(acted) => {
            if (!acted) grid.current?.focusCell(overview.key, overview.column);
          }}
        />
      )}
      <Toast className="ledger-toast">{toast}</Toast>
    </div>
  );
}
