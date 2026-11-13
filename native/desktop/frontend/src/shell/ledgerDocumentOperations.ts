// The window's names for the request and result of the ledger operations on
// documents: evidence records, the readings drafted from them and their
// confirmation, the attachments waiting for review, the pages of a stored
// document and the consent survey. Each is the registered Python contract's
// own type, taken from the generated modules by definition id, so no field is
// written here. A request leaves out the profile, which the host fills, and
// the folder it fills for a chosen document.

import type { LedgerDocumentContracts } from "./ledgerDocumentContract";
import type { LedgerDocumentReviewContracts } from "./ledgerDocumentReviewContract";

type Contracts = LedgerDocumentContracts & LedgerDocumentReviewContracts;
type Definition = keyof Contracts;

/** What the window sends: the registered request without the profile and
 * without the `Host` fields the host fills. */
type Sent<D extends Definition, Host extends string = never> = Omit<
  Contracts[D]["request"],
  "profile_id" | Host
>;

/** What the operation serves. */
type Served<D extends Definition> = Contracts[D]["result"];

export type EvidenceAddRequest = Sent<
  "ledger.evidence.add",
  "source_directory"
>;
export type EvidenceListResult = Served<"ledger.evidence.list">;
export type EvidenceViewRequest = Sent<"ledger.evidence.view">;
export type EvidenceViewResult = Served<"ledger.evidence.view">;
export type EvidenceUpdateRequest = Sent<"ledger.evidence.update">;
export type EvidenceRemoveRequest = Sent<"ledger.evidence.remove">;

/** A record added, corrected or removed. */
export type EvidenceRecordResult =
  | Served<"ledger.evidence.add">
  | Served<"ledger.evidence.update">
  | Served<"ledger.evidence.remove">;

export type EvidenceBatchRequest = Sent<
  "ledger.evidence.batch",
  "source_directory"
>;
export type EvidenceBatchResult = Served<"ledger.evidence.batch">;

export type EvidenceReviewListRequest = Sent<"ledger.evidence.review.list">;
export type EvidenceReviewListResult = Served<"ledger.evidence.review.list">;
export type EvidenceReviewViewRequest = Sent<"ledger.evidence.review.view">;
export type EvidenceReviewViewResult = Served<"ledger.evidence.review.view">;
export type EvidenceExtractRequest = Sent<"ledger.evidence.extract">;
export type EvidenceExtractResult = Served<"ledger.evidence.extract">;
export type EvidenceConfirmRequest = Sent<"ledger.evidence.confirm">;
export type EvidenceConfirmResult = Served<"ledger.evidence.confirm">;

export type AttachmentQueueResult = Served<"ledger.evidence.attachment_queue">;
export type AttachmentViewRequest = Sent<"ledger.evidence.attachment_view">;
export type AttachmentViewResult = Served<"ledger.evidence.attachment_view">;
export type EvidencePageRequest = Sent<"ledger.evidence.page">;
export type EvidencePageResult = Served<"ledger.evidence.page">;
export type EvidenceConsentListResult = Served<"ledger.evidence.consent.list">;
