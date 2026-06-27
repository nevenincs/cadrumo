---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-06-25'
modified: '2026-06-25'
step_id: 'S10'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---




# Extend the golden-SHA fichero roundtrip with a REDEME-1 plus IBAN-populated case, per-offset assertions grounded against the DR303 offsets (110, DID 12, 23, 194)

## Scope

- `src/aeat/adapters/outbound/aeat/export/_formats/tests/test_fichero_boe_roundtrip.py`

## Description

- Regenerate the non-refund Modelo 303 golden-SHA case from the real serialiser after the P02 wiring changed its output: the REDEME indicator byte now appears at page-1 offset 110 and the empty cuenta-devolucion (DID) page is suppressed on a non-refund disposition, dropping the fichero from 7994 to 7171 bytes.
- Capture the regenerated non-refund SHA from genuine export output and update the golden constant; never hand-tune the hash.
- Add a per-offset assertion that the REDEME indicator at page-1 offset 110 is the byte 2 (NO) for the ordinary non-REDEME filer, passing the redeme header the M303 composer emits for a non-enrolled profile.
- Replace the now-suppressed DID per-offset assertions with byte-level assertions that the DID open tag and the DID00 page identifier are absent from a non-refund filing, and assert the receipt byte size is 7171.
- Add a new refund golden case driving a refund disposition with a Spanish IBAN: assert the per-offset DR303-expected values independently of the SHA — the REDEME indicator at offset 110 is the byte 1 (SI), the IBAN sits at DID offset 23 left-justified, the SWIFT-BIC at DID offset 12 stays blank for a SEPA account, and the derived Marca SEPA at DID offset 194 is the byte 1 (Cuenta Espana) for an ES IBAN.
- Capture the refund case SHA from the real serialiser, assert the 7994-byte length, and confirm the IBAN appears exactly once and only inside the DID page.
- Ground every offset against the DR303 Diseno via the 303 export registry layout (REDEME 110, DID SWIFT 12 / IBAN 23 / SEPA 194, all carrying source_refs aeat-dr-303-2025).

## Outcome

- The non-refund golden SHA is regenerated to `e9dfc7d11988d4bd0aa0ea4f540440c28da287ee3f832a2baec2183740a48113` (length 7171, DID suppressed) and the new refund golden SHA is `a95880caf0dd5b43e787b907d9e1ec20ea829aca1a1aaca12876490db11a730f` (length 7994, DID emitted).
- The whole roundtrip file is green (14 passed); ruff, ruff-format, and ty are clean on the changed file; the 303 registry loads cleanly.
- The per-offset value assertions are the anti-tautology anchor: they assert the DR303-prescribed bytes for the supplied refund account, not that the fichero round-trips its own output.

## Notes

- The casilla-id type-sweep (str to CasillaId) being landed concurrently by a peer is confirmed OUTPUT-BYTE-NEUTRAL: both golden SHAs and every per-offset value assertion hold identically with the sweep present in the working tree. A type annotation does not change an emitted string, and the byte-identity locks would have failed if it did.
- The non-refund REDEME byte at offset 110 is the byte 2 only because the test now passes the redeme header explicitly (the value the M303 composer emits for a non-REDEME filer); without that header the serialiser-level field pads to a blank space, which is the honest serialiser default. The header is supplied so the golden case asserts the composed indicator rather than the unset default.
