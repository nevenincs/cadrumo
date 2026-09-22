# LEDGER-01 correction and audit decision packet

Status: both decisions accepted by the user on 2026-09-22. Decision A selects explicit linked-ID edit refusal for LEDGER-01; Decision B selects atomic durable invoice catalogue and audit write. Current safe behavior refuses a linked transaction ID change before persistence. No live data or filing action is involved.

## Evidence and boundary

- Transaction IDs are derived from record content. Edit lineage records a previous ID and read-side resolution follows it. The current manual update carries `invoice_id` onto a replacement, but does not rewrite the invoice's `linked_transaction_ids`.
- Explicit link creation already co-commits reciprocal transaction/invoice catalogues and its event in the secure-object batch. The combined invoice/transaction/event helper does not currently provide an expected invoice revision. A linked identity edit therefore lacks a defined revision-guarded write path.
- Invoice create/update currently saves the encrypted catalogue, then emits the bucket event separately. An event failure can leave a durable invoice and an exception to the caller. Retrying create can meet the duplicate-ID guard while the audit event remains absent. The accepted decisions cover historical-ID read resolution, atomic link creation and canonical invoice preservation, but do not specify correction or event recovery.

## Decision A — linked transaction identity edit

**Accepted for LEDGER-01: option 1, retain refusal.** Both frontends must report the same unsupported linked-ID correction outcome. An unlinked edit may follow its existing validated path. Option 2 remains only a future design candidate and is not authorized for this lane.

1. **Retain refusal for this lane.** CLI and TUI expose the same typed refusal and direct the operator to a supported correction procedure once defined. This preserves current consistency but does not deliver an identity-changing linked edit.
2. **Authorize a linked correction contract.** Define an atomic, revision-guarded write of the replacement transaction, invoice's old-to-new linked ID swap, edit lineage, evidence references and durable audit intent. The old ID continues to resolve by accepted read lineage; prior canonical facts and evidence remain reconstructable. Validation rejects missing source, stale baseline, ID collision, wrong bucket/entity and invalid tax/FX facts before mutation. Retry converges to one correction and cannot overwrite a concurrent invoice edit.

The same batch must include every related record named above, or the operation must refuse. A payment record or tax-return amendment is outside this choice. The accepted link-creation mechanism is a precedent, not an approved correction policy.

## Decision B — invoice create/update event failure

**Accepted: option 1, atomic durable audit history.** The invoice catalogue and audit event/intent must commit together under guarded revisions. A failed batch leaves neither write committed; a successful batch returns the committed identity and event reference. Notification delivery policy remains outside this decision and is not inferred.

1. **Atomic durable audit history.** Save the invoice catalogue and durable audit event/intent together under guarded revisions. Delivery of a later notification may retry separately. A failed batch leaves neither write committed; a successful batch returns the committed identity and event reference.
2. **Explicit recoverable partial outcome.** Keep save-then-emit but return a typed committed-with-audit-pending result if event emission fails. Define a deterministic repair operation and idempotency key so retry records exactly one event without duplicating or overwriting the invoice. Both frontends must show the committed invoice and pending audit state rather than report a plain failure or phantom success.

Either choice must specify event identity, concurrent create/update behavior and historical payload retention. An event count or delivery acknowledgement does not prove recoverable prior invoice content.

## Immediate implementation boundary

Implement the accepted invoice-and-audit atomic write through the existing secure-object co-commit boundary. Keep the linked-ID guard and do not claim an identity-changing correction. Continue independent import, custody, field-parity and installed frontend work where ownership permits.

## Separate import identity question

Current bulk import deduplicates by the content-derived invoice ID. A changed total under the same printed number/date/counterparty therefore creates another catalogue record, while a renamed file with identical content is correctly skipped. A conflict key cannot be inferred solely from a printed number: the issuing entity, series and date matter, and the received-invoice book also distinguishes issuer data from the local receipt number. The [BOE invoicing regulation article 6](https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696) requires invoice number and where applicable series; the [AEAT received-invoice register](https://sede.agenciatributaria.gob.es/Sede/iva/facturacion-registro/libros-registro-iva/libro-registro-facturas-recibidas.html) records issuer identification and the document's dates. AEAT's [SII technical FAQ](https://sede.agenciatributaria.gob.es/Sede/impuestos-tasas/iva/iva-libros-registro-iva-traves-aeat/preguntas-tecnicas-frecuentes.html) describes an SII record key of issuer NIF, series-number and issue date, but SII is outside this ledger brief and does not automatically define this catalogue's conflict policy. Decide separately whether a same-business-identity/different-content import must refuse, enter a review queue, or coexist as a documented correction; define the exact issuer/entity/year/series/date scope and treatment of missing data before changing deduplication.
