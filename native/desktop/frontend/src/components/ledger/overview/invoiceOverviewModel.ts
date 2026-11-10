// An invoice's overview: what the catalogue stores for it, in the words the
// Invoices grid and editor use. Totals are the stored ones; nothing is added
// up here.

import { facts } from "../../../shell/compose";
import type { PublicDecimal } from "../../../shell/ledger";
import type { CatalogueInvoice } from "../../../shell/ledgerInvoiceOperations";
import type { Translate } from "../../../shell/strings";
import { formatDay } from "../../../shared/dateFormats";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import { seriesAndNumber } from "../invoices/invoiceModel";
import { settlesText } from "../matching/matchingWords";
import { classLabel, kindLabel, paymentLabel } from "../invoices/invoiceWords";
import { ivaCategoryLabel } from "../movements/movementWords";
import {
  absent,
  stored,
  unknown,
  type OverviewChip,
  type OverviewFact,
  type OverviewModel,
  type OverviewValue,
} from "./overviewModel";

const money = (
  locale: string,
  value: PublicDecimal | null,
  notSet: string,
  currency?: string,
): OverviewValue =>
  value === null
    ? absent(notSet)
    : stored(
        formatAmount(locale, value.decimal, currency ? { currency } : {}),
        {
          figure: true,
        },
      );

function chipsOf(t: Translate, invoice: CatalogueInvoice): OverviewChip[] {
  const status = invoice.payment_status;
  return [
    {
      id: "payment",
      text: paymentLabel(t, status),
      tone:
        status === "PAID"
          ? "success"
          : status === "OVERDUE"
            ? "warning"
            : "neutral",
      ...(status === "OVERDUE" ? { icon: "alert" as const } : {}),
    },
    { id: "kind", text: kindLabel(t, invoice.kind), tone: "neutral" },
  ];
}

/** The overview of one catalogue invoice. */
export function invoiceOverview(
  t: Translate,
  locale: string,
  invoice: CatalogueInvoice,
): OverviewModel {
  const notSet = t("desktop.ledger.inspector.not_set");
  const foreign = invoice.currency !== "EUR";
  const converted: OverviewValue | null = !foreign
    ? null
    : invoice.grand_total_eur === null
      ? unknown(
          facts(t, [
            t("desktop.ledger.inspector.no_rate"),
            t("desktop.ledger.inspector.no_rate_detail"),
          ]),
        )
      : stored(
          formatAmount(locale, invoice.grand_total_eur.decimal, {
            currency: "EUR",
          }),
          {
            figure: true,
            detail: invoice.fx_rate
              ? facts(t, [
                  t("desktop.ledger.inspector.fx_rate", {
                    rate: invoice.fx_rate.decimal,
                  }),
                  invoice.fx_rate_date
                    ? formatDay(locale, invoice.fx_rate_date)
                    : null,
                  invoice.fx_rate_source,
                ])
              : undefined,
          },
        );

  const amounts: OverviewFact[] = [
    {
      id: "base_total",
      label: t("desktop.ledger.invoices.column.base"),
      value: money(locale, invoice.base_total, notSet),
    },
    {
      id: "iva_total",
      label: t("desktop.ledger.invoices.column.iva"),
      value: money(locale, invoice.iva_total, notSet),
    },
  ];
  if (invoice.recargo_amount !== null)
    amounts.push({
      id: "recargo_amount",
      label: t("desktop.ledger.invoices.field.recargo"),
      value: money(locale, invoice.recargo_amount, notSet),
    });
  if (invoice.retention_amount !== null || invoice.retention_rate !== null)
    amounts.push({
      id: "retention_amount",
      label: t("desktop.ledger.invoices.field.retention_amount"),
      value:
        invoice.retention_amount === null
          ? absent(notSet)
          : stored(formatAmount(locale, invoice.retention_amount.decimal), {
              figure: true,
              detail: invoice.retention_rate
                ? formatPercent(locale, invoice.retention_rate.decimal, {
                    unit: "fraction",
                  })
                : undefined,
            }),
    });
  amounts.push({
    id: "grand_total",
    label: t("desktop.ledger.invoices.column.total"),
    value: money(locale, invoice.grand_total, notSet),
  });

  const classification: OverviewFact[] = [
    {
      id: "invoice_class",
      label: t("desktop.ledger.invoices.field.invoice_class"),
      value: stored(classLabel(t, invoice.invoice_class)),
    },
    {
      id: "iva_category",
      label: t("desktop.ledger.invoices.field.iva_category"),
      value: invoice.iva_category
        ? stored(ivaCategoryLabel(t, invoice.iva_category))
        : absent(notSet),
    },
    {
      id: "operation_date",
      label: t("desktop.ledger.invoices.field.operation_date"),
      value: invoice.operation_date
        ? stored(formatDay(locale, invoice.operation_date), { figure: true })
        : absent(notSet),
    },
  ];
  if (invoice.operation_type)
    classification.push({
      id: "operation_type",
      label: t("desktop.ledger.invoices.field.operation_type"),
      value: stored(
        t("desktop.ledger.invoices.operation_key", {
          key: invoice.operation_type,
        }),
      ),
    });
  if (invoice.rectifies_invoice_number)
    classification.push({
      id: "rectifies_invoice_number",
      label: t("desktop.ledger.invoices.field.rectifies_invoice_number"),
      value: stored(invoice.rectifies_invoice_number),
    });

  const linked = invoice.linked_transaction_ids.length;
  return {
    kind: "invoice",
    kindLabel: t("desktop.ledger.overview.kind.invoice"),
    title: invoice.counterparty_name,
    subtitle: facts(t, [
      seriesAndNumber(invoice),
      formatDay(locale, invoice.issued_at),
    ]),
    amount: {
      text: formatAmount(locale, invoice.grand_total.decimal, {
        currency: invoice.currency,
      }),
      detail: t("desktop.ledger.invoices.column.total"),
      ...(converted
        ? {
            converted: {
              label: t("desktop.ledger.inspector.eur_value"),
              value: converted,
            },
          }
        : {}),
    },
    chips: chipsOf(t, invoice),
    notice: null,
    groups: [
      {
        id: "amounts",
        heading: t("desktop.ledger.overview.group.amounts"),
        facts: amounts,
        // What it settles, in the words the matching queue says it with.
        notes: [
          {
            text: settlesText(
              t,
              locale,
              invoice,
              invoice.settlement_amount.decimal,
            ),
            tone: "neutral",
          },
        ],
      },
      {
        id: "classification",
        heading: t("desktop.ledger.inspector.classification"),
        facts: classification,
      },
      {
        id: "counterparty",
        heading: t("desktop.ledger.invoices.field.counterparty_name"),
        facts: [
          {
            id: "counterparty_tax_id",
            label: t("desktop.ledger.invoices.field.counterparty_tax_id"),
            value: invoice.counterparty_tax_id
              ? stored(invoice.counterparty_tax_id, { figure: true })
              : absent(t("desktop.ledger.invoices.none")),
          },
          {
            id: "counterparty_country",
            label: t("desktop.ledger.invoices.field.counterparty_country"),
            value: invoice.counterparty_country
              ? stored(invoice.counterparty_country)
              : absent(t("desktop.ledger.inspector.not_stated")),
          },
        ],
      },
      {
        id: "links",
        heading: t("desktop.ledger.overview.group.links"),
        facts: [
          {
            id: "linked_transaction_ids",
            label: t("desktop.ledger.invoices.column.linked"),
            value:
              linked === 0
                ? absent(t("desktop.ledger.invoices.unmatched"))
                : stored(
                    t("desktop.ledger.invoices.linked_count", {
                      count: linked,
                    }),
                  ),
          },
        ],
      },
      {
        id: "origin",
        heading: t("desktop.ledger.overview.group.origin"),
        facts: [
          {
            id: "source",
            label: t("desktop.ledger.inspector.came_from"),
            value: invoice.source_filename
              ? stored(
                  invoice.source_row_index === null
                    ? invoice.source_filename
                    : t("desktop.ledger.inspector.file_row", {
                        file: invoice.source_filename,
                        row: invoice.source_row_index,
                      }),
                )
              : stored(t("desktop.ledger.inspector.added_by_hand")),
          },
          {
            id: "notes",
            label: t("desktop.ledger.invoices.field.notes"),
            value: invoice.notes
              ? stored(invoice.notes)
              : absent(t("desktop.ledger.inspector.not_set")),
          },
        ],
      },
    ],
  };
}
