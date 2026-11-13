// A document's overview: an evidence record as the ledger stores it, what
// waits on its reading, and the movement it is attached to. The record's
// facts are what the person or a confirmed reading stated; a reading waiting
// for review is a proposal, said as such.

import { facts } from "../../../shell/compose";
import type { LedgerRow } from "../../../shell/ledger";
import type { LedgerEvidenceRecordProjection } from "../../../shell/ledgerDocumentContract";
import type { EvidenceReviewQueueRowProjection } from "../../../shell/ledgerDocumentReviewContract";
import { EVIDENCE_UPDATE_FIELDS } from "../../../shell/ledgerContract";
import type { Translate } from "../../../shell/strings";
import {
  formatDay,
  formatInstantDay,
  formatTime,
} from "../../../shared/dateFormats";
import { formatAmount, formatPercent } from "../../../shared/numbers";
import { fileName, recordValue } from "../documents/documentsModel";
import { reasonLabel } from "../documents/documentWords";
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

/** What is known of a record's reading waiting for review: the queue's row
 * for it, none, or that the queue could not be read. */
export type DocumentReading =
  | { kind: "waiting"; row: EvidenceReviewQueueRowProjection }
  | { kind: "none" }
  | { kind: "unknown" };

/** The movement a record is attached to; unknown while the period's
 * movements are not read. A record names no movement itself, so one not
 * found among the period's is said to be not attached in this period, never
 * not attached at all. */
export type DocumentAttachment =
  | { kind: "attached"; row: LedgerRow }
  | { kind: "not_found" }
  | { kind: "unknown" };

export type DocumentOverviewInput = {
  t: Translate;
  locale: string;
  record: LedgerEvidenceRecordProjection;
  reading: DocumentReading;
  attachment: DocumentAttachment;
};

function recordFact(
  t: Translate,
  locale: string,
  record: LedgerEvidenceRecordProjection,
  field: (typeof EVIDENCE_UPDATE_FIELDS)[number],
): OverviewFact {
  const raw = recordValue(record, field);
  const label = t(`desktop.ledger.documents.record.${field}`);
  let value: OverviewValue;
  if (raw === null || raw === "")
    value = absent(t("desktop.ledger.documents.nothing_stated"));
  else if (field === "invoice_date")
    value = stored(formatDay(locale, raw), { figure: true });
  else if (field === "taxable_base" || field === "iva_amount")
    value = stored(formatAmount(locale, raw), { figure: true });
  // A record's rate is stored in points, as the record editor takes it.
  else if (field === "iva_rate")
    value = stored(formatPercent(locale, raw, { unit: "points" }), {
      figure: true,
    });
  else value = stored(raw);
  return { id: field, label, value };
}

function readingGroup(input: DocumentOverviewInput): OverviewGroup {
  const { t, locale, reading } = input;
  const heading = t("desktop.ledger.overview.group.reading");
  if (reading.kind === "unknown")
    return {
      id: "reading",
      heading,
      facts: [
        {
          id: "reading",
          label: heading,
          value: unknown(t("desktop.ledger.inspector.unread")),
        },
      ],
    };
  if (reading.kind === "none")
    return {
      id: "reading",
      heading,
      facts: [],
      notes: [
        { text: t("desktop.ledger.overview.no_reading"), tone: "neutral" },
      ],
    };
  const row = reading.row;
  return {
    id: "reading",
    heading,
    facts: [
      {
        id: "drafted_at",
        label: heading,
        value: stored(
          t("desktop.ledger.overview.reading_waiting", {
            date: formatInstantDay(locale, row.drafted_at),
          }),
        ),
      },
    ],
    notes:
      row.blocking_count > 0
        ? (row.reasons ?? []).length > 0
          ? (row.reasons ?? []).map((_, at) => ({
              text: reasonLabel(t, row.reason_words?.[at]),
              tone: "warning" as const,
            }))
          : [
              {
                text: t("desktop.ledger.documents.findings_open", {
                  count: row.blocking_count,
                }),
                tone: "warning" as const,
              },
            ]
        : [
            {
              text: t("desktop.ledger.documents.ready_to_confirm"),
              tone: "neutral" as const,
            },
          ],
  };
}

function chipsOf(input: DocumentOverviewInput): OverviewChip[] {
  const { t, record, reading } = input;
  const chips: OverviewChip[] = [
    {
      id: "media",
      text: t(`desktop.ledger.documents.media.${record.media_kind}`),
      tone: "neutral",
      icon: record.media_kind === "image" ? "image" : "page",
    },
  ];
  if (reading.kind === "waiting")
    chips.push(
      reading.row.blocking_count > 0
        ? {
            id: "reading",
            text: t("desktop.ledger.documents.findings_open", {
              count: reading.row.blocking_count,
            }),
            tone: "warning",
            icon: "alert",
          }
        : {
            id: "reading",
            text: t("desktop.ledger.documents.in_review"),
            tone: "neutral",
          },
    );
  return chips;
}

/** The overview of one evidence record. */
export function documentOverview(input: DocumentOverviewInput): OverviewModel {
  const { t, locale, record, attachment } = input;
  const name = fileName(record.source_path);
  const attached: OverviewValue =
    attachment.kind === "unknown"
      ? unknown(t("desktop.ledger.loading"))
      : attachment.kind === "not_found"
        ? absent(t("desktop.ledger.overview.not_attached_here"))
        : stored(
            attachment.row.transaction.description ||
              attachment.row.transaction.counterparty,
            {
              detail: facts(t, [
                formatAmount(locale, attachment.row.transaction.amount, {
                  currency: attachment.row.transaction.currency,
                }),
                formatDay(locale, attachment.row.transaction.date),
              ]),
            },
          );
  return {
    kind: "document",
    kindLabel: t("desktop.ledger.overview.kind.document"),
    title: name,
    subtitle:
      facts(t, [
        record.supplier,
        record.invoice_number,
        record.invoice_date ? formatDay(locale, record.invoice_date) : null,
      ]) || t("desktop.ledger.documents.nothing_stated"),
    amount: null,
    chips: chipsOf(input),
    notice: null,
    groups: [
      {
        id: "recorded",
        heading: t("desktop.ledger.overview.group.recorded"),
        facts: EVIDENCE_UPDATE_FIELDS.map((field) =>
          recordFact(t, locale, record, field),
        ),
      },
      readingGroup(input),
      {
        id: "links",
        heading: t("desktop.ledger.overview.group.links"),
        facts: [
          {
            id: "attached_to",
            label: t("desktop.ledger.overview.kind.movement"),
            value: attached,
          },
        ],
      },
      {
        id: "origin",
        heading: t("desktop.ledger.overview.group.origin"),
        facts: [
          {
            id: "created_at",
            label: t("desktop.ledger.inspector.added"),
            value: stored(formatTime(locale, record.created_at), {
              figure: true,
            }),
          },
          {
            id: "updated_at",
            label: t("desktop.ledger.inspector.last_saved"),
            value: stored(formatTime(locale, record.updated_at), {
              figure: true,
            }),
          },
        ],
      },
    ],
  };
}
