import { servedLimits } from "./support/servedLimits";
import { holdLedgerLimits } from "../src/shell/ledgerLimits";
import { expect, test } from "@playwright/test";
import type {
  ConfirmationBlockerProjectionV1,
  InvoiceDraftProjectionV1,
} from "../src/shell/ledgerDocumentReviewContract";
import type { LedgerEvidenceRecordProjection } from "../src/shell/ledgerDocumentContract";
import {
  confirmation,
  correctionValues,
  duplicateQuestion,
  findingsState,
  holdsUpdate,
  recordUpdate,
  readCorrection,
  resolutionOf,
  sameReading,
} from "../src/components/ledger/documents/documentsModel";
import { EMPTY_DRAFT } from "../src/dev/ledgerEvidenceSeed";
import { hexId } from "./support/ledger";

// The Documents section's rules: a confirmation always names its kind and
// country, sends only corrections that change the reading, in the
// confirmation's own spelling, and every finding's answer; the catalogue's
// duplicate is found by number first; a record's correction sends what
// changed. Every value is invented.

const draft: InvoiceDraftProjectionV1 = {
  ...EMPTY_DRAFT,
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
const blocker: ConfirmationBlockerProjectionV1 = {
  blocker_id: "0123456789abcdef",
  reason: "ambiguous_identity",
  field: "supplier_tax_id",
  detail: "Two tax ids.",
  candidates: [
    { value: "B12000045", anchor: null, note: "" },
    { value: "B12000046", anchor: null, note: "" },
  ],
  reason_words: null,
  reason_words_language: null,
  words: null,
  detail_words: null,
  detail_words_language: null,
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

test("a retención is sent in points, for the ledger to turn into its fraction", () => {
  const confirmed = (retention_rate: string) => {
    const result = confirmation({
      reference: { kind: "evidence", id: "e-1" },
      binding: {
        sourceSha256: "a".repeat(64),
        draftReviewSha256: "b".repeat(64),
      },
      draft,
      blockers: [],
      answers: {},
      kind: "received",
      country: "ES",
      corrections: { retention_rate, retention_amount: "150" },
      duplicate: null,
      confirmAnyway: false,
    });
    if (result.kind !== "ready") throw new Error("held");
    return result.request;
  };
  // One typed means one per cent, not the whole.
  expect(confirmed("1").retention_points).toBe("1");
  expect(confirmed("1").retention_rate).toBeUndefined();
  expect(confirmed("0.5").retention_points).toBe("0.5");
  expect(confirmed("0.5").retention_amount).toBe("150");
});

test("saying the retención the document printed is still saying it", () => {
  const read = {
    ...draft,
    retencion_rate: { decimal: "15" },
    retencion_amount: { decimal: "150.00" },
  };
  expect(
    correctionValues(read as typeof draft, "received", {
      retention_rate: "15",
      retention_amount: "150.00",
    }),
  ).toEqual({
    kind: "ok",
    values: { retention_rate: "15", retention_amount: "150" },
  });
  expect(correctionValues(read as typeof draft, "received", {})).toEqual({
    kind: "ok",
    values: {},
  });
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

test("the duplicate question states what the reading says, corrected, once a kind is chosen", () => {
  expect(duplicateQuestion(draft, null, {})).toBeNull();
  const asked = duplicateQuestion(draft, "received", {})!;
  expect(asked.kind).toBe("received");
  expect(asked.invoice_number).toBe(draft.invoice_number);
  expect(
    duplicateQuestion(draft, "received", { invoice_number: "PT-0999" })!
      .invoice_number,
  ).toBe("PT-0999");
});

test("a confirmation waits while the ledger has yet to say if the reading is in the catalogue", () => {
  const held = confirmation({
    reference,
    binding,
    draft,
    blockers: [],
    answers: {},
    kind: "received",
    country: "ES",
    corrections: {},
    duplicate: null,
    duplicateUnread: true,
    confirmAnyway: false,
  });
  expect(held.kind).toBe("held");
  expect(held.kind === "held" && held.holds).toContain("duplicate_unread");
});

test("a fresh reading equal to the one shown is the reading reviewed", () => {
  expect(sameReading(draft, { ...draft })).toBe(true);
  expect(sameReading(draft, { ...draft, raw_text_length: 1 })).toBe(false);
});

test("a record's correction sends only what changed and clears with a blank", () => {
  const record: LedgerEvidenceRecordProjection = {
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
  // A record's label and note are held to what the ledger serves, and to
  // nothing while it serves nothing.
  const served = (name: string) =>
    servedLimits.text_limits.find((found) => found.name === name)!.max;
  expect(
    recordUpdate(record, {
      supplier: "x".repeat(served("evidence_label") + 1),
    }),
  ).toEqual({ kind: "refused", fields: ["supplier"] });
  expect(
    recordUpdate(record, { notes: "x".repeat(served("evidence_note") + 1) }),
  ).toEqual({ kind: "refused", fields: ["notes"] });
  expect(
    recordUpdate(record, { notes: "x".repeat(served("evidence_note")) }).kind,
  ).toBe("update");
  holdLedgerLimits(null);
  try {
    expect(recordUpdate(record, { notes: "una nota" })).toEqual({
      kind: "refused",
      fields: ["notes"],
    });
  } finally {
    holdLedgerLimits(servedLimits);
  }
  if (update.kind !== "update") throw new Error("no update");
  expect(holdsUpdate(record, update.request)).toBe(false);
  expect(
    holdsUpdate(
      { ...record, supplier: null, iva_amount: "6.30", iva_rate: "10" },
      update.request,
    ),
  ).toBe(true);
});

test("a supplied finding value is held to the confirmation's served bound, and to none while it serves nothing", () => {
  const bound = servedLimits.text_limits.find(
    (found) => found.name === "confirm_label",
  )!.max;
  const supplied = (value: string) =>
    resolutionOf(blocker, { action: "supply_value", value, note: "" });
  expect(supplied("x".repeat(bound))).not.toBeNull();
  expect(supplied("x".repeat(bound + 1))).toBeNull();
  try {
    holdLedgerLimits(null);
    expect(supplied("x")).toBeNull();
    expect(readCorrection("invoice_number", "x")).toEqual({
      kind: "refused",
      refusal: { key: "limits_unavailable", raw: "x" },
    });
  } finally {
    holdLedgerLimits(servedLimits);
  }
});
