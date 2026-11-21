// The scenario ledger's check of a document's stored file and its release
// of a movement's purchase document, held to the registered contracts of
// `ledger.evidence.verify` and `ledger.purchase_evidence.release`. A check
// keeps what it found on the record; a release is decided against the
// evidence and the modification time the person's opened movement showed,
// and every refusal names its cause and the step that follows, as the
// backend's does. Everything it answers is synthetic.

import type { JsonObject } from "../shell/ledger";
import type {
  PurchaseEvidenceReleaseCause,
  PurchaseEvidenceReleaseNextStep,
} from "../shell/ledgerInvoiceContract";
import {
  readableFile,
  type FixtureLedger,
  type FixtureMovement,
} from "./fixtures/ledger";
import { InvoiceStopped } from "./ledgerInvoiceFixture";
import { invalid, text } from "./ledgerRequestFixture";

declare global {
  interface Window {
    /** Controls for what the scenario's movements cannot get from a person
     * in this window. */
    __scenarioMovements?: {
      /** Changes every movement described `description`, as another
       * window saving them would, without this window reading them again. */
      change(description: string): void;
    };
  }
}

type Tools = {
  profileId: string;
  events: () => string[];
  now: () => string;
};

const NEXT_STEP: Record<
  PurchaseEvidenceReleaseCause,
  PurchaseEvidenceReleaseNextStep
> = {
  transaction_not_found: "reopen_transaction",
  no_linked_purchase_evidence: "reopen_transaction",
  transaction_changed: "reopen_transaction",
  transaction_not_editable: "restore_transaction",
  finalized_calculation_reference: "reopen_finalized_calculation",
  evidence_confirmed_into_invoice: "link_movement_to_invoice",
  reference_has_no_stored_document: "detach_instead",
};

const made = new Set<(description: string) => void>();

export function purchaseReleaseOperations(
  ledger: FixtureLedger,
  { profileId, events, now }: Tools,
) {
  const change = (description: string) => {
    for (const movement of ledger.movements)
      if (movement.transaction.description === description)
        movement.transaction.modified_at = now();
  };
  made.add(change);
  window.__scenarioMovements = {
    change: (description) => made.forEach((one) => one(description)),
  };

  function verify(request: JsonObject): JsonObject {
    const wanted = text(request.evidence_id);
    if (!wanted || wanted.length > 64) invalid();
    const record = ledger.evidence.find(
      (found) => found.evidence_id === wanted,
    );
    if (!record)
      throw new InvoiceStopped("REFUSED_LEDGER_EVIDENCE_NOT_FOUND", {
        profile_id: profileId,
        outcome: { kind: "refused", evidence_record_present: false },
      });
    // The scenario's stored files are all ones a reader recognises.
    Object.assign(record, readableFile(record.media_kind, now()));
    return {
      profile_id: profileId,
      outcome: {
        kind: "checked",
        record: {
          ...(record as unknown as JsonObject),
          source_path: record.source_path.split(/[\\/]/).pop() ?? "",
        },
        bucket_event_ids: events(),
      },
    };
  }

  function release(request: JsonObject): JsonObject {
    const prefix = text(request.transaction_id)?.toLowerCase();
    const expectedEvidence = text(
      request.expected_purchase_invoice_evidence_id,
    );
    const expectedModified = text(request.expected_modified_at);
    const disposition =
      request.disposition === "detach" ||
      request.disposition === "keep_as_document"
        ? request.disposition
        : null;
    if (!prefix || !expectedEvidence || !expectedModified || !disposition)
      invalid();
    const refuse = (cause: PurchaseEvidenceReleaseCause): never => {
      throw new InvoiceStopped("REFUSED_LEDGER_PURCHASE_EVIDENCE_RELEASE", {
        outcome: "refused",
        profile_id: profileId,
        disposition,
        released_evidence_id: expectedEvidence,
        transaction: null,
        review_status: null,
        bucket_event_ids: [],
        refusal: {
          cause,
          next_step: NEXT_STEP[cause],
          finalized_revisions: [],
          invoice_ids: [],
        },
      });
    };
    const found = ledger.movements.filter((movement) =>
      movement.transaction.transaction_id.startsWith(prefix!),
    );
    if (found.length !== 1) refuse("transaction_not_found");
    const movement: FixtureMovement = found[0]!;
    const t = movement.transaction;
    if (t.purchase_invoice_evidence_id !== expectedEvidence)
      refuse("no_linked_purchase_evidence");
    if (t.modified_at !== expectedModified) refuse("transaction_changed");
    if (t.lifecycle_state !== "ACTIVE") refuse("transaction_not_editable");
    if (movement.sealed) refuse("finalized_calculation_reference");
    const record = ledger.evidence.find(
      (candidate) => candidate.evidence_id === expectedEvidence,
    );
    if (!record && disposition === "keep_as_document")
      refuse("reference_has_no_stored_document");
    t.purchase_invoice_evidence_id = null;
    if (
      disposition === "keep_as_document" &&
      record &&
      !t.attachment_ids.includes(record.attachment_id)
    )
      t.attachment_ids = [...t.attachment_ids, record.attachment_id];
    t.modified_at = now();
    return {
      outcome: "updated",
      profile_id: profileId,
      disposition,
      released_evidence_id: expectedEvidence,
      transaction: { ...t } as unknown as JsonObject,
      review_status:
        t.business_classification === "NOT_YET_PROCESSED"
          ? "pending"
          : "reviewed",
      bucket_event_ids: events(),
      refusal: null,
    };
  }

  return {
    writes: {
      "ledger.evidence.verify": verify,
      "ledger.purchase_evidence.release": release,
    } satisfies Record<string, (request: JsonObject) => JsonObject>,
  };
}
