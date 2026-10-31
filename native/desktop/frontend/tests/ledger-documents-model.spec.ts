import { expect, test } from "@playwright/test";
import type {
  CatalogueInvoice,
  ConfirmationBlocker,
  EvidenceDraft,
  EvidenceRecord,
} from "../src/shell/ledger";
import {
  confirmation,
  correctionValues,
  duplicateOf,
  findingsState,
  holdsUpdate,
  recordUpdate,
  resolutionOf,
  sameReading,
} from "../src/components/ledger/documents/documentsModel";
import { hexId } from "./support/ledger";

// The Documents section's rules: a confirmation always names its kind and
// country, sends only corrections that change the reading, in the
// confirmation's own spelling, and every finding's answer; the catalogue's
// duplicate is found by number first; a record's correction sends what
// changed. Every value is invented.

const draft: EvidenceDraft = {
  supplier_name: "Papelería Trazo SL",
  supplier_tax_id: "B12000045",
  supplier_country_code: "ES",
  invoice_number: "PT-0412",
  invoice_date: "2026-10-15",
  taxable_base: { decimal: "30.00" },
  iva_rate: { decimal: "21" },
  iva_amount: { decimal: "6.30" },
  grand_total: { decimal: "36.30" },
  currency: "EUR",
  provenance: [],
};
const blocker: ConfirmationBlocker = {
  blocker_id: "0123456789abcdef",
  reason: "ambiguous_identity",
  field: "supplier_tax_id",
  detail: "Two tax ids.",
  candidates: [{ value: "B12000045" }, { value: "B12000046" }],
};
const binding = {
  sourceSha256: hexId("source"),
  draftReviewSha256: hexId("reading"),
};
const reference = { kind: "evidence", id: "e1" } as const;

test("a confirmation names its kind and country, and is held until both are given", () => {
  const base = {
    reference,
    binding,
    draft,
    blockers: [],
    answers: {},
    corrections: {},
    duplicate: null,
    confirmAnyway: false,
  };
  expect(confirmation({ ...base, kind: null, country: "" })).toEqual({
    kind: "held",
    holds: ["choose_kind", "country"],
  });
  expect(
    confirmation({ ...base, kind: "received", country: "ESP" }),
  ).toMatchObject({ kind: "held", holds: ["country"] });
  expect(confirmation({ ...base, kind: "received", country: "es" })).toEqual({
    kind: "ready",
    request: {
      evidence_id: "e1",
      expected_source_sha256: binding.sourceSha256,
      expected_draft_review_sha256: binding.draftReviewSha256,
      kind: "received",
      counterparty_country: "ES",
    },
  });
});

test("only corrections that change the reading are sent, in the confirmation's spelling", () => {
  expect(
    correctionValues(draft, "received", {
      taxable_base: "30",
      iva_rate: "21%",
      invoice_number: "PT-0412",
      iva_amount: "6.40",
      retention_rate: "15",
      counterparty_tax_id: "B12000046",
    }),
  ).toEqual({
    kind: "ok",
    values: {
      iva_amount: "6.4",
      retention_rate: "15",
      counterparty_tax_id: "B12000046",
    },
  });
  expect(
    correctionValues(draft, "received", { taxable_base: "30,00" }),
  ).toEqual({ kind: "refused", fields: ["taxable_base"] });
  // A counterparty correction means nothing before the kind says whose.
  expect(
    correctionValues(draft, null, { counterparty_name: "Otra SL" }),
  ).toEqual({ kind: "ok", values: {} });
});

test("a rate is read as points, so half a point is not mistaken for a fraction", () => {
  expect(
    correctionValues(draft, "received", { retention_rate: "0.5" }),
  ).toEqual({ kind: "ok", values: { retention_rate: "0.5" } });
  expect(correctionValues(draft, "received", { iva_rate: "100.5" })).toEqual({
    kind: "refused",
    fields: ["iva_rate"],
  });
});

test("a finding is answered by a candidate it offers, a value, or an attestation with a reason", () => {
  expect(resolutionOf(blocker, undefined)).toBeNull();
  expect(
    resolutionOf(blocker, {
      action: "choose_candidate",
      value: "B99999999",
      note: "",
    }),
  ).toBeNull();
  expect(
    resolutionOf(blocker, {
      action: "choose_candidate",
      value: "B12000046",
      note: "",
    }),
  ).toEqual({
    blocker_id: blocker.blocker_id,
    action: "choose_candidate",
    value: "B12000046",
    note: "",
  });
  expect(
    resolutionOf(blocker, { action: "attest", value: "x", note: "  " }),
  ).toBeNull();
  expect(
    resolutionOf(blocker, {
      action: "attest",
      value: "x",
      note: "Printed so.",
    }),
  ).toEqual({
    blocker_id: blocker.blocker_id,
    action: "attest",
    value: null,
    note: "Printed so.",
  });
  const state = findingsState([blocker], {});
  expect(state.open).toEqual([blocker]);
  const held = confirmation({
    reference,
    binding,
    draft,
    blockers: [blocker],
    answers: {},
    kind: "received",
    country: "ES",
    corrections: {},
    duplicate: null,
    confirmAnyway: false,
  });
  expect(held).toEqual({ kind: "held", holds: ["findings"] });
});

function catalogued(
  number: string,
  facts: Partial<CatalogueInvoice> = {},
): CatalogueInvoice {
  return {
    invoice_id: hexId(number),
    bucket_id: null,
    kind: "received",
    invoice_number: number,
    issued_at: "2026-10-15",
    counterparty_name: "Papelería Trazo SL",
    counterparty_tax_id: "B12000045",
    counterparty_country: "ES",
    base_total: { decimal: "30.00" },
    iva_total: { decimal: "6.30" },
    grand_total: { decimal: "36.30" },
    currency: "EUR",
    payment_status: "PENDING",
    linked_transaction_ids: [],
    source_filename: null,
    source_sha256: null,
    source_row_index: null,
    notes: "",
    retention_rate: null,
    retention_amount: null,
    recargo_amount: null,
    operation_type: null,
    lines: [],
    invoice_class: "ORDINARIA",
    series: null,
    operation_date: null,
    operation_date_role: null,
    iva_category: null,
    rectifies_invoice_number: null,
    fx_rate: null,
    fx_rate_date: null,
    fx_rate_source: null,
    base_total_eur: null,
    iva_total_eur: null,
    grand_total_eur: null,
    ...facts,
  };
}

test("the catalogue's duplicate is the same number first, then the same party, day and total", () => {
  const sameDay = catalogued("PT-0999");
  const sameNumber = catalogued("pt 0412", { issued_at: "2026-01-01" });
  const otherKind = catalogued("PT-0412", { kind: "issued" });
  expect(duplicateOf(draft, "received", {}, [sameDay, sameNumber])).toBe(
    sameNumber,
  );
  expect(duplicateOf(draft, "received", {}, [sameDay])).toBe(sameDay);
  expect(duplicateOf(draft, "received", {}, [otherKind])).toBeNull();
  const otherParty = catalogued("PT-0412", {
    counterparty_tax_id: "B00000000",
  });
  expect(duplicateOf(draft, "received", {}, [otherParty])).toBeNull();
  expect(duplicateOf(draft, null, {}, [sameNumber])).toBeNull();
  // A corrected number is the one compared.
  expect(
    duplicateOf(draft, "received", { invoice_number: "PT-0999" }, [sameDay]),
  ).toBe(sameDay);
});

test("a fresh reading equal to the one shown is the reading reviewed", () => {
  expect(sameReading(draft, { ...draft })).toBe(true);
  expect(sameReading(draft, { ...draft, raw_text_length: 1 })).toBe(false);
});

test("a record's correction sends only what changed and clears with a blank", () => {
  const record: EvidenceRecord = {
    evidence_id: "e1",
    bucket_id: "b",
    source_sha256: hexId("s"),
    attachment_id: hexId("s"),
    media_kind: "pdf",
    supplier: "Trazo",
    invoice_number: "PT-1",
    invoice_date: null,
    taxable_base: "30",
    iva_rate: "21",
    iva_amount: null,
    notes: "",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    source_path: "factura.pdf",
  };
  expect(
    recordUpdate(record, { taxable_base: "30.00", iva_rate: "21" }),
  ).toEqual({ kind: "unchanged" });
  const update = recordUpdate(record, {
    supplier: "",
    iva_amount: "6.30",
    iva_rate: "10%",
  });
  expect(update).toEqual({
    kind: "update",
    request: {
      evidence_id: "e1",
      patch: { supplier: null, iva_amount: "6.3", iva_rate: "10" },
      patch_fields: ["supplier", "iva_amount", "iva_rate"],
    },
  });
  expect(recordUpdate(record, { invoice_date: "15/10/2026" })).toEqual({
    kind: "refused",
    fields: ["invoice_date"],
  });
  if (update.kind !== "update") throw new Error("no update");
  expect(holdsUpdate(record, update.request)).toBe(false);
  expect(
    holdsUpdate(
      { ...record, supplier: null, iva_amount: "6.30", iva_rate: "10" },
      update.request,
    ),
  ).toBe(true);
});
