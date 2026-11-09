// A movement's overview: what the stored movement and the page's readiness
// check already say of it, in the words the grid and the inspector use. It
// works nothing out: a tax fact is shown as stored, or as not set.

import { facts, listed, noted } from "../../../shell/compose";
import type { LedgerRow } from "../../../shell/ledger";
import { takesBusinessShare } from "../../../shell/ledgerClassifications";
import { isDecidedClassification } from "../../../shell/ledgerContract";
import type { LedgerTrackResult } from "../../../shell/ledgerMovementOperations";
import type { OwnAccountChoice } from "../../../shell/ledgerMovementReads";
import type { Translate } from "../../../shell/strings";
import { formatDay, formatTime } from "../../../shared/dateFormats";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import { fieldName, valueText } from "../editing/editingWords";
import type { InspectorRead } from "../inspector/useInspectorReads";
import {
  declarationName,
  decidedBy,
  revisionStateLabel,
} from "../inspector/inspectorWords";
import { needsInvoice } from "../movements/movementsModel";
import {
  accountLabel,
  categoryLabel,
  classificationText,
  directionLabel,
  lifecycleLabel,
  reasonDetail,
  statusLabel,
  statusWord,
} from "../movements/movementWords";
import {
  absent,
  stored,
  unknown,
  type OverviewChip,
  type OverviewFact,
  type OverviewGroup,
  type OverviewModel,
  type OverviewValue,
} from "./overviewModel";

/** The tax facts a movement carries, in the order the grid's columns show
 * them. */
const TAX_FIELDS = [
  "iva_category",
  "taxable_base",
  "iva_rate",
  "iva_amount",
  "deduction_fact_kind",
  "irpf_category",
] as const;

export type MovementOverviewInput = {
  t: Translate;
  locale: string;
  row: LedgerRow;
  /** What readiness found on the movement; null until it was measured. */
  issues: readonly string[] | null;
  /** An import flagged it as a likely duplicate. */
  duplicate: boolean;
  /** The register's own accounts, null while unread. */
  accounts: readonly Pick<OwnAccountChoice, "id" | "label">[] | null;
  /** How many changes to it are staged and not saved. */
  unsaved: number;
  /** Where it came from and which declarations cite it; null while it is
   * not asked for. */
  track: InspectorRead<LedgerTrackResult> | null;
};

/** The EUR value of a movement in another currency: stored, or unknown
 * for want of a rate, which is never zero. */
function euroValue(
  t: Translate,
  locale: string,
  row: LedgerRow,
): OverviewValue | null {
  const tx = row.transaction;
  if (tx.currency === "EUR") return null;
  if (tx.value_in_eur === null)
    return unknown(
      facts(t, [
        t("desktop.ledger.inspector.no_rate"),
        t("desktop.ledger.inspector.no_rate_detail"),
      ]),
    );
  return stored(formatAmount(locale, tx.value_in_eur, { currency: "EUR" }), {
    figure: true,
    detail: tx.fx_rate
      ? t("desktop.ledger.inspector.fx_rate", { rate: tx.fx_rate })
      : null,
  });
}

function chipsOf(input: MovementOverviewInput): OverviewChip[] {
  const { t, row, issues, duplicate } = input;
  const counted = issues === null ? null : issues.length;
  const word = statusWord(row.review_status, counted);
  const chips: OverviewChip[] = [
    {
      id: "status",
      text: statusLabel(t, word, counted),
      tone:
        word === "done"
          ? "success"
          : word === "needs_fixing"
            ? "warning"
            : "neutral",
      ...(word === "needs_fixing" ? { icon: "alert" as const } : {}),
    },
  ];
  const state = row.transaction.lifecycle_state;
  if (state !== "ACTIVE")
    chips.push({
      id: "lifecycle",
      text: lifecycleLabel(t, state),
      tone: "neutral",
    });
  if (duplicate)
    chips.push({
      id: "duplicate",
      text: t("desktop.ledger.import_issue.duplicate"),
      tone: "warning",
      icon: "copy",
    });
  return chips;
}

function classificationGroup(input: MovementOverviewInput): OverviewGroup {
  const { t, locale, row } = input;
  const tx = row.transaction;
  const notSet = t("desktop.ledger.inspector.not_set");
  const decided = isDecidedClassification(tx.business_classification);
  const list: OverviewFact[] = [
    {
      id: "business_classification",
      label: t("desktop.ledger.column.classification"),
      value: decided
        ? stored(classificationText(t, locale, tx))
        : absent(classificationText(t, locale, tx)),
    },
  ];
  if (takesBusinessShare(tx.business_classification) === true)
    list.push({
      id: "business_pct",
      label: t("desktop.ledger.inspector.share"),
      value:
        tx.business_pct === null
          ? absent(notSet)
          : stored(
              formatPercent(locale, tx.business_pct, { unit: "fraction" }),
              {
                figure: true,
              },
            ),
    });
  list.push({
    id: "category_id",
    label: t("desktop.ledger.column.category"),
    value: tx.category_id
      ? stored(categoryLabel(t, tx.category_id))
      : absent(notSet),
  });
  const by = decidedBy(t, tx.classified_by);
  list.push({
    id: "classified_by",
    label: t("desktop.ledger.column.classified_by"),
    value:
      tx.classified_by === "" || tx.classified_by === "none"
        ? absent(by)
        : stored(by, {
            detail: tx.classified_at
              ? formatTime(locale, tx.classified_at)
              : null,
          }),
  });
  if (tx.classification_reason)
    list.push({
      id: "classification_reason",
      label: t("desktop.ledger.overview.reason"),
      value: stored(tx.classification_reason),
    });
  return {
    id: "classification",
    heading: t("desktop.ledger.inspector.classification"),
    facts: list,
  };
}

function taxGroup(input: MovementOverviewInput): OverviewGroup {
  const { t, locale, row } = input;
  const tx = row.transaction;
  const heading = t("desktop.ledger.overview.group.tax");
  const held = TAX_FIELDS.filter((field) => tx[field] !== null);
  // None stored: one line says so, rather than six that each say not set.
  if (held.length === 0)
    return {
      id: "tax",
      heading,
      facts: [],
      notes: [
        { text: t("desktop.ledger.overview.no_tax_facts"), tone: "neutral" },
      ],
    };
  return {
    id: "tax",
    heading,
    facts: TAX_FIELDS.map((field) => {
      const value = tx[field];
      return {
        id: field,
        label: fieldName(t, field),
        value:
          value === null
            ? absent(t("desktop.ledger.inspector.not_set"))
            : stored(valueText(t, locale, field, value), {
                figure:
                  field === "taxable_base" ||
                  field === "iva_rate" ||
                  field === "iva_amount",
              }),
      };
    }),
  };
}

function linksGroup(input: MovementOverviewInput): OverviewGroup {
  const { t, row } = input;
  const tx = row.transaction;
  const documents =
    (tx.purchase_invoice_evidence_id ? 1 : 0) + tx.attachment_ids.length;
  return {
    id: "links",
    heading: t("desktop.ledger.overview.group.links"),
    facts: [
      {
        id: "invoice_id",
        label: t("desktop.ledger.column.invoice"),
        value: tx.invoice_id
          ? stored(t("desktop.ledger.invoice.linked"))
          : absent(
              needsInvoice(row)
                ? noted(
                    t,
                    t("desktop.ledger.overview.not_linked"),
                    t("desktop.ledger.filters.to_match"),
                  )
                : t("desktop.ledger.overview.not_linked"),
            ),
      },
      {
        id: "documents",
        label: t("desktop.ledger.column.documents"),
        value:
          documents === 0
            ? absent(t("desktop.ledger.inspector.documents.none"))
            : stored(
                t("desktop.ledger.documents.count", { count: documents }),
                {
                  detail: tx.purchase_invoice_evidence_id
                    ? t("desktop.ledger.inspector.documents.purchase_linked")
                    : null,
                },
              ),
      },
    ],
  };
}

function originGroup(input: MovementOverviewInput): OverviewGroup {
  const { t, locale, row, accounts, track } = input;
  const tx = row.transaction;
  const tracked = track?.kind === "ready" ? track.result : null;
  const provenance = tracked?.imported_provenance ?? null;
  const cameFrom: OverviewValue =
    track === null || track.kind === "reading"
      ? unknown(t("desktop.ledger.loading"))
      : track.kind === "failed"
        ? unknown(t("desktop.ledger.inspector.unread"))
        : provenance
          ? stored(
              t("desktop.ledger.inspector.file_row", {
                file: provenance.source_filename,
                row: provenance.source_row_index,
              }),
              {
                detail: facts(t, [
                  provenance.provider_name,
                  formatTime(locale, provenance.ingested_at),
                ]),
              },
            )
          : stored(t("desktop.ledger.inspector.added_by_hand"));
  const list: OverviewFact[] = [
    {
      id: "source",
      label: t("desktop.ledger.inspector.came_from"),
      value: cameFrom,
    },
    {
      id: "own_account_id",
      label: t("desktop.ledger.field.own_account_id"),
      value:
        row.own_account_id === null
          ? absent(accountLabel(t, accounts, null))
          : stored(accountLabel(t, accounts, row.own_account_id)),
    },
  ];
  // The declarations that cite it, where the ledger keeps that index. One
  // never built is not the same as none.
  const uses = tracked?.participated_in;
  if (tracked !== null)
    list.push({
      id: "participated_in",
      label: t("desktop.ledger.overview.used_in"),
      value:
        uses === null || uses === undefined
          ? unknown(t("desktop.ledger.unavailable"))
          : uses.length === 0
            ? absent(t("desktop.ledger.overview.used_nowhere"))
            : stored(
                listed(
                  t,
                  uses.map((use) =>
                    noted(
                      t,
                      declarationName(
                        t,
                        use.modelo,
                        use.period.filing_year,
                        use.period.code,
                      ),
                      revisionStateLabel(t, use),
                    ),
                  ),
                ),
              ),
    });
  list.push(
    {
      id: "created_at",
      label: t("desktop.ledger.inspector.added"),
      value: stored(formatTime(locale, tx.created_at), { figure: true }),
    },
    {
      id: "modified_at",
      label: t("desktop.ledger.inspector.last_saved"),
      value: stored(formatTime(locale, tx.modified_at), { figure: true }),
    },
  );
  return {
    id: "origin",
    heading: t("desktop.ledger.overview.group.origin"),
    facts: list,
  };
}

function readinessGroup(input: MovementOverviewInput): OverviewGroup {
  const { t, issues } = input;
  const heading = t("desktop.ledger.readiness.title");
  if (issues === null)
    return {
      id: "readiness",
      heading,
      facts: [
        {
          id: "readiness",
          label: heading,
          value: unknown(t("desktop.ledger.readiness.not_measured")),
        },
      ],
    };
  if (issues.length === 0)
    return {
      id: "readiness",
      heading,
      facts: [],
      notes: [
        { text: t("desktop.ledger.overview.nothing_to_fix"), tone: "neutral" },
      ],
    };
  return {
    id: "readiness",
    heading,
    facts: [],
    notes: issues.map((reason) => ({
      text: reasonDetail(t, reason),
      tone: "warning",
    })),
  };
}

/** The overview of one stored movement. */
export function movementOverview(input: MovementOverviewInput): OverviewModel {
  const { t, locale, row, unsaved } = input;
  const tx = row.transaction;
  const euro = euroValue(t, locale, row);
  return {
    kind: "movement",
    kindLabel: t("desktop.ledger.overview.kind.movement"),
    title:
      tx.description ||
      tx.counterparty ||
      t("desktop.ledger.inspector.not_set"),
    subtitle: facts(t, [
      tx.counterparty || t("desktop.ledger.inspector.no_counterparty"),
      formatDay(locale, tx.date),
    ]),
    amount: {
      text: formatAmount(locale, tx.amount, { currency: tx.currency }),
      detail: directionLabel(t, tx.direction),
      ...(euro
        ? {
            converted: {
              label: t("desktop.ledger.inspector.eur_value"),
              value: euro,
            },
          }
        : {}),
    },
    chips: chipsOf(input),
    notice:
      unsaved > 0
        ? t("desktop.ledger.inspector.unsaved", { count: unsaved })
        : null,
    groups: [
      classificationGroup(input),
      taxGroup(input),
      linksGroup(input),
      originGroup(input),
      readinessGroup(input),
    ],
  };
}
