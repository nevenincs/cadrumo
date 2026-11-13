import { expect, test } from "@playwright/test";
import {
  documentAttachmentReference,
  movementDocuments,
} from "../src/components/ledger/inspector/movementDocuments";
import { effectiveFacts, storedFieldValue } from "../src/shell/ledgerStage";
import type { LedgerEvidenceRecordProjection } from "../src/shell/ledgerDocumentContract";
import { hexId, movement } from "./support/ledger";

const record: LedgerEvidenceRecordProjection = {
  evidence_id: hexId("e"),
  bucket_id: "synthetic-profile",
  source_sha256: hexId("b"),
  attachment_id: hexId("b"),
  media_kind: "pdf",
  supplier: null,
  invoice_number: null,
  invoice_date: null,
  taxable_base: null,
  iva_rate: null,
  iva_amount: null,
  notes: "",
  source_path: "synthetic-purchase.pdf",
  created_at: "2026-02-20T12:00:00Z",
  updated_at: "2026-02-20T12:00:00Z",
};

test("linked purchase evidence is shown even without a supplementary attachment", () => {
  const row = movement(hexId("a"), {
    purchase_invoice_evidence_id: record.evidence_id,
    attachment_ids: [],
  });
  expect(movementDocuments(row.transaction, [record])).toEqual({
    purchase: { evidenceId: record.evidence_id, record },
    supplementary: [],
  });
});

test("purchase evidence's blob is displayed once and supplementary attachments retain their own detach list", () => {
  const extra = hexId("c");
  const row = movement(hexId("a"), {
    purchase_invoice_evidence_id: record.evidence_id,
    attachment_ids: [record.attachment_id, extra],
  });
  const documents = movementDocuments(row.transaction, [record]);
  expect(documents.purchase?.record).toEqual(record);
  expect(documents.supplementary).toEqual([extra]);
});

test("unloaded or missing evidence details do not erase the known purchase reference", () => {
  const row = movement(hexId("a"), {
    purchase_invoice_evidence_id: record.evidence_id,
    attachment_ids: [],
  });
  expect(movementDocuments(row.transaction, []).purchase).toEqual({
    evidenceId: record.evidence_id,
    record: null,
  });
});

test("an unrelated evidence catalogue record does not invent a movement link", () => {
  const row = movement(hexId("a"));
  expect(movementDocuments(row.transaction, [record])).toEqual({
    purchase: null,
    supplementary: [],
  });
});

test("a later document supplements immutable purchase evidence instead of replacing it", () => {
  const row = movement(hexId("a"), {
    purchase_invoice_evidence_id: hexId("f"),
  });
  expect(documentAttachmentReference(row.transaction, record)).toEqual({
    evidenceId: null,
    attachmentIds: [record.attachment_id],
  });
  expect(
    documentAttachmentReference({ purchase_invoice_evidence_id: null }, record),
  ).toEqual({ evidenceId: record.evidence_id, attachmentIds: [] });
});

test("ordinary stored deduction and investment facts survive a new inspector read", () => {
  const row = movement(hexId("a"), {
    deduction_fact_kind: "domestic_current",
    investment_asset_id: "synthetic-asset",
  });
  expect(storedFieldValue(row, "deduction_fact_kind")).toBe("domestic_current");
  expect(storedFieldValue(row, "investment_asset_id")).toBe("synthetic-asset");
  expect(effectiveFacts(row, undefined).deduction_fact_kind).toBe(
    "domestic_current",
  );
  expect(
    effectiveFacts(row, {
      deduction_fact_kind: { kind: "set", value: "domestic_investment" },
    }).deduction_fact_kind,
  ).toBe("domestic_investment");
  expect(row.transaction.deduction_fact_kind).toBe("domestic_current");
});
