import { expect, test } from "@playwright/test";
import type { LedgerEvidenceRecordProjection } from "../src/shell/ledgerDocumentContract";
import type { EvidenceReviewQueueRowProjection } from "../src/shell/ledgerDocumentReviewContract";
import { documentOverview } from "../src/components/ledger/overview/documentOverviewModel";
import type { Translate } from "../src/shell/strings";
import { hexId } from "./support/ledger";
import { label } from "./support/strings";

// A document's overview says whether its reading is ready to confirm. While
// the profile lacks a fact no confirmation can go without, a reading with no
// finding of its own is not ready: the overview shows the sentence the backend
// served instead. Every value is synthetic.

const t = Object.assign(
  (key: string, values?: Record<string, string | number>) =>
    label(key, values, "en"),
  { locale: "en" },
) as Translate;

const record: LedgerEvidenceRecordProjection = {
  evidence_id: "e1",
  bucket_id: "bucket",
  source_sha256: hexId("source"),
  attachment_id: hexId("attachment"),
  media_kind: "pdf",
  supplier: "Papelería Trazo SL",
  invoice_number: "PT-0412",
  invoice_date: "2026-10-15",
  taxable_base: "30.00",
  iva_rate: "21",
  iva_amount: "6.30",
  notes: "",
  created_at: "2026-10-15T09:00:00Z",
  updated_at: "2026-10-15T09:00:00Z",
  readability: "unchecked",
  document_shape: null,
  unreadable_cause: null,
  readability_checked_at: null,
  source_path: "C:/Documentos/factura-trazo.pdf",
};
const row: EvidenceReviewQueueRowProjection = {
  evidence_reference: "e1",
  extractor: "text_layer",
  drafted_at: "2026-10-15T10:00:00Z",
  blocking_count: 0,
  reasons: [],
  reason_words: [],
  reason_words_language: null,
  advisory_count: 0,
  advisories: [],
};
const STATED = "The profile does not state the postcode of its fiscal address.";

const reading = (
  waiting: Partial<{
    row: EvidenceReviewQueueRowProjection;
    precondition: string | null;
  }>,
) =>
  documentOverview({
    t,
    locale: "en",
    record,
    reading: { kind: "waiting", row, precondition: null, ...waiting },
    attachment: { kind: "unknown" },
  });
const notesOf = (model: ReturnType<typeof documentOverview>) =>
  model.groups.find((group) => group.id === "reading")?.notes ?? [];
const chipOf = (model: ReturnType<typeof documentOverview>) =>
  model.chips.find((chip) => chip.id === "reading");

test("a reading with no finding is ready to confirm while the profile lacks nothing", () => {
  const model = reading({});
  expect(notesOf(model)).toEqual([
    {
      text: label("desktop.ledger.documents.ready_to_confirm"),
      tone: "neutral",
    },
  ]);
  expect(chipOf(model)?.tone).toBe("neutral");
});

test("a reading with no finding is not ready while the profile lacks a fact every confirmation needs", () => {
  const model = reading({ precondition: STATED });
  expect(notesOf(model)).toEqual([{ text: STATED, tone: "warning" }]);
  expect(JSON.stringify(model)).not.toContain(
    label("desktop.ledger.documents.ready_to_confirm"),
  );
  expect(chipOf(model)?.tone).toBe("warning");
});

test("a reading's own findings are said as they are, whatever the profile lacks", () => {
  const model = reading({
    precondition: STATED,
    row: {
      ...row,
      blocking_count: 2,
      reasons: ["ambiguous_identity", "closure_discrepancy"],
      reason_words: ["Two tax ids compete.", "The total does not close."],
    },
  });
  expect(notesOf(model).map((note) => note.text)).toEqual([
    "Two tax ids compete.",
    "The total does not close.",
  ]);
  expect(JSON.stringify(model)).not.toContain(STATED);
});
