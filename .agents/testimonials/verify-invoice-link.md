# Verify: INVOICE ↔ TRANSACTION LINK flow (M17 fix)

Date: 2026-06-19
Persona env: /tmp/verify-invoice-link
Verdict: **PASS** — the link flow works end-to-end. The M17 break (no way to create a
linkable rich invoice) is fixed by `ledger invoice catalogue create`. One minor
inconsistency noted (prefix resolution on `link --invoice-id`); not a flow break.

## Setup

- Profile 1: `verify-link` (natural_person, 12345678Z) — created OK, exit 0.
- Profile 2: `verify-link-2` (87654321X) — created OK (for cross-bucket probe).
- Ledger tx (profile 1): `461c1978…` (OUTGOING 1210.00, 2026-01-15) — created OK, exit 0.

## Results

### 1. Create rich catalogue invoice — PASS
- Cmd: `ledger invoice catalogue create --kind received --counterparty-nif B12345674 --counterparty-name "Proveedor SL" --invoice-number FAC-2026-001 --invoice-date 2026-01-15 --taxable-base 1000.00 --iva-rate 21`
- Expected: invoice created with an id usable by `link --invoice-id`.
- Actual: `invoice_id  e28ac9e5…`, `grand_total 1210.00`, `linked_transaction_ids` empty. Exit 0.
- Notes (boundary, not failures): `--iva-rate 0.21` rejected ("not a recognised IVA percentage"); `21` accepted. NIF checksum is enforced (`B12345678` rejected "CIF digit-control checksum is invalid"); used a valid CIF `B12345674`.

### 2. Link tx → invoice — PASS (M17 fix confirmed)
- Cmd (prefix): `ledger link 461c1978… --invoice-id e28ac9e5… --by verifier`
  - Actual: REFUSED, exit 2 — "Este id no existe en el catálogo…". **Prefix not resolved by `link --invoice-id`.**
- Cmd (full ids): `ledger link <full-tx> --invoice-id <full-invoice> --by verifier`
  - Expected: succeed.
  - Actual: `operation ledger.link … invoice_id e28ac9e5…`. **Exit 0.** SUCCESS.

### 3. Bidirectionality — PASS (with caveat)
- `invoice catalogue view e28ac9e5…` → `linked_transaction_ids 461c1978…`. Exit 0. (invoice → tx ✓)
- `ledger view 461c1978…` → does NOT print the linked catalogue-invoice id. The tx
  side has no "linked invoice" field in the text view; only "Evidencia de factura de
  compra" (the evidence path, separate) is shown. `--json` is not available on `ledger view`.
  - Caveat: the data model stores the link on the invoice side only (the tx→invoice
    relation is computed by scanning the catalogue, e.g. `_actions_lifecycle.py:421-423`),
    and tx removal correctly cascades the detach — so the relationship IS bidirectional
    in the store. The gap is presentation: `ledger view` does not surface linked catalogue
    invoices. (Minor UX gap, not a flow break.)

### 4. Link non-existent invoice id — PASS (refused)
- Cmd: `ledger link <tx> --invoice-id ffff…ffff`
- Expected: refuse. Actual: REFUSED, exit 2 ("Este id no existe en el catálogo…"). ✓

### 5. Cross-bucket link — PASS (refused)
- Setup: profile 2 invoice `52cf2ee5…`; `config switch verify-link` back to profile 1.
- Cmd: `ledger link <p1-tx> --invoice-id <p2-invoice> --by verifier`
- Expected: still refuse (intentional guard). Actual: REFUSED, exit 2. ✓
  - Mechanism: catalogue is bucket-scoped, so p2's id is not in p1's catalogue and the
    not-found refusal fires (the explicit `cross_bucket_invoice` message at
    `_ledger.py:795` is a defence-in-depth second guard). Either way, correctly refused.

### 6. Remove a LINKED invoice — PASS (refused "unlink first")
- Cmd: `ledger invoice catalogue remove e28ac9e5… --yes` (while linked)
- Expected: refuse with unlink guidance. Actual: exit 1 —
  "No se puede eliminar la factura … mientras siga vinculada a transacciones: 461c1978…. Desvincúlelas primero." ✓

### 7. Unlink, then remove — PASS (implicit unlink via tx removal)
- No dedicated unlink verb exists (`ledger` has no `unlink`/`detach`; the `link` verb
  has only `--invoice-id`/`--evidence-id` add-flags). The remove error's "Desvincúlelas
  primero" / docstring "the operator must `link`-unlink first" implies a verb that is
  not present. **Minor gap: guidance references an unlink path with no matching CLI verb.**
- Unlink IS achievable implicitly by removing the transaction (cascades the detach):
  - `ledger remove 461c1978… --yes` → exit 0; afterwards
    `catalogue view e28ac9e5…` shows `linked_transaction_ids` empty. ✓
  - `ledger invoice catalogue remove e28ac9e5… --yes` → exit 0 (now unlinked);
    `catalogue list` → `count 0`. ✓

### 8. `link --evidence-id` (purchase-evidence path) — PASS
- Setup: `ledger evidence add /tmp/fac.pdf --supplier "Proveedor SL" --invoice-number EV-001 --invoice-date 2026-01-15 --taxable-base 500.00 --iva-rate 0.21` → `evidence_id e35ed160cc5a4571`, exit 0.
- Cmd: `ledger link 461c1978… --evidence-id e35ed160cc5a4571 --by verifier` → exit 0.
- `ledger view 461c1978…` → "Evidencia de factura de compra  e35ed160cc5a4571". ✓ Bidirectional + visible on tx.
- Note (boundary): `evidence add` accepts `--iva-rate 0.21` (decimal) whereas `catalogue create` wants `21`. Inconsistent rate convention across the two verbs (not in scope).

## Summary of non-blocking observations
1. `link --invoice-id` does NOT accept an unambiguous prefix (requires full 64-char id),
   while `catalogue view`/`remove` DO accept prefixes. Inconsistent UX.
2. `ledger view` does not surface the linked catalogue-invoice id on the transaction
   side (only the evidence path). Relationship is correct in storage; presentation gap.
3. The "unlink first" refusal message / docstring references an unlink verb that does
   not exist as a CLI command; unlinking only happens implicitly via tx removal.
4. IVA-rate convention differs between `catalogue create` (`21`) and `evidence add` (`0.21`).

All core requirements pass: rich invoice creation, link success, refusal of non-existent
and cross-bucket links, refusal to remove a linked invoice, unlink+remove lifecycle, and
the `--evidence-id` path.
