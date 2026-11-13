// The window's names for the request and result of the ledger operations on
// the invoice catalogue: list, add, preview, correct, remove, import, the
// duplicate and match checks, the links between movements and invoices, and
// the attachments and checks of a movement. Each is the registered Python
// contract's own type, taken from the generated module by definition id, so
// no field is written here. A request leaves out the profile, which the host
// fills, and the folder it fills for a chosen document.

import type { LedgerInvoiceContracts } from "./ledgerInvoiceContract";

type Definition = keyof LedgerInvoiceContracts;

/** What the window sends: the registered request without the profile and
 * without the `Host` fields the host fills. */
type Sent<D extends Definition, Host extends string = never> = Omit<
  LedgerInvoiceContracts[D]["request"],
  "profile_id" | Host
>;

/** What the operation serves. */
type Served<D extends Definition> = LedgerInvoiceContracts[D]["result"];

export type InvoiceListRequest = Sent<"ledger.invoice.list">;
export type InvoiceListResult = Served<"ledger.invoice.list">;
export type InvoiceAddRequest = Sent<"ledger.invoice.add">;
export type InvoiceAddResult = Served<"ledger.invoice.add">;
export type InvoicePreviewRequest = Sent<"ledger.invoice.preview">;
export type InvoicePreviewResult = Served<"ledger.invoice.preview">;
export type InvoiceUpdateRequest = Sent<"ledger.invoice.update">;
export type InvoiceUpdateResult = Served<"ledger.invoice.update">;
export type InvoiceRemoveRequest = Sent<"ledger.invoice.remove">;
export type InvoiceRemoveResult = Served<"ledger.invoice.remove">;
export type InvoiceViewRequest = Sent<"ledger.invoice.view">;
export type InvoiceViewResult = Served<"ledger.invoice.view">;

export type InvoiceDocumentAttachRequest = Sent<
  "ledger.invoice.attach_document",
  "source_directory"
>;
export type InvoiceDocumentAttachResult =
  Served<"ledger.invoice.attach_document">;
export type InvoiceImportRequest = Sent<"ledger.invoice.import">;
export type InvoiceImportResult = Served<"ledger.invoice.import">;

export type LedgerInvoiceDuplicateRequest = Sent<"ledger.invoice.duplicate">;
export type LedgerInvoiceDuplicateResult = Served<"ledger.invoice.duplicate">;
export type LedgerInvoiceMatchRequest = Sent<"ledger.invoice.match">;
export type LedgerInvoiceMatchResult = Served<"ledger.invoice.match">;

export type LedgerLinkRequest = Sent<"ledger.link">;
export type LedgerLinkResult = Served<"ledger.link">;
export type LedgerAttachRequest = Sent<"ledger.attach">;
export type LedgerDetachRequest = Sent<"ledger.detach">;
export type LedgerAttachResult = Served<"ledger.attach">;
export type LedgerCheckRequest = Sent<"ledger.check">;
export type LedgerCheckResult = Served<"ledger.check">;
