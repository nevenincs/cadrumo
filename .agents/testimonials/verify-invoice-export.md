# Testimonial: invoice/evidence survives into the filing artefact (real CLI)

Persona: thorough user verifying INVOICE/EVIDENCE links survive a full 303 chain.
Env: `/tmp/verify-invoice-export`, profile `testautonomo` (natural_person, NIF 12345678Z,
name "Juan Perez Garcia", activity-start 2026-01-01). All commands via
`uv run --no-sync aeat ...`. Verdict: **PASS** (all 3 axes + edges hold).

## Setup chain (all exit 0)
- `config profile create testautonomo --quiet --accept-defaults --entity-type natural_person --tax-id 12345678Z` -> created.
- `ledger evidence add invoice.pdf --supplier ... --invoice-number INV-001 --taxable-base 1000 --iva-rate 0.21 --iva-amount 210` -> `evidence_id f363cbe8c3f64e36`, `source_sha256 df257009...` (bytes captured, media_kind pdf).
- `ledger add --date 2026-01-15 --amount 1210 --direction OUTGOING --classification BUSINESS --category-id material_oficina --taxable-base 1000 --iva-rate 0.21 --iva-amount 210 --purchase-invoice-evidence-id f363cbe8c3f64e36` -> tx `3a3be22b...`.

## (a) Evidence link persists on the transaction — PASS
- Cmd: `ledger view 3a3be22b`
- Expected: evidence id present on tx.
- Actual (exit 0): `Evidencia de factura de compra	f363cbe8c3f64e36`.
- Verdict: PASS.

## (b) Export carries evidence into the filing evidence — PASS
- Chain: `work create 303/2026/1T` -> `work calculate` (IVA soportado 315.00 = 210+105 from both BUSINESS expenses flowed in; casilla 64 / iva.resultado = -315.00 compensacion) -> `work verify` (after recording activity-start-date 2026-01-01 to scope out the prior-period dependency: `completeness_status complete`, `granted_verificado_completo true`) -> `modelo export ... --output m303.txt`.
- Cmd: `aeat app modelo export <wu> --modelo 303 --year 2026 --period 1T --output m303.txt`
- Expected: export of a ledger-derived revision succeeds only if bundled evidence present.
- Actual (exit 0): `format fichero-boe`, `byte_size 7994`, `file_sha256 5ed4e11b...`.
- Code-grounded: verify persists `ledger_filing_evidence` into the encrypted revision via `compute_ledger_filing_evidence` (`_verification_actions.py:1289`); `LedgerEvidenceRow.purchase_invoice_evidence_id` populated from the tx (`_ledger_filing_snapshot.py:175`); export refuses a ledger-derived revision lacking bundled evidence (`_export.py:569 _raise_if_ledger_export_evidence_missing`). Export succeeded => the gate passed => `ledger_filing_evidence is not None`.
- Note: fichero-BOE itself (the AEAT submission file) contains only casilla values, NOT evidence (grep for `f363cbe8`/`df257009` = 0 hits) — correct: AEAT's fichero never bundles evidence; evidence rides inside the encrypted revision envelope + workbook `Evidencia` surface per ledger-derived-revisions-bundle-evidence.
- Verdict: PASS.

## (c) evidence-bytes-not-links holds (doclink/url refused, bytes required) — PASS
- Cmd: `ledger doclink eb77d12b --source URL --reference https://example.com/invoice.pdf`
- Expected: refused; bytes required.
- Actual (exit 0, Invalid value): "la evidencia debe contener los bytes cifrados del documento, y un enlace nunca se guarda por si solo. Descarga el documento y adjuntalo con 'aeat app ledger attach --attachment-id ...'".
- Same refusal for `--source GMAIL --reference msg-123`.
- Verdict: PASS (upholds ledger-evidence-bytes-not-links).

## Edge probes
- Attach NON-EXISTENT evidence id to a clean tx: `ledger attach eb77d12b --purchase-invoice-evidence-id deadbeefdeadbeef` -> refused (exit 0, Invalid value): "purchase_invoice_evidence_id must reference an existing purchase invoice evidence record..."; `ledger view` confirms tx still has NO evidence. PASS.
- Attach evidence to NON-EXISTENT tx: `ledger attach ffffffffffffffff ...` -> refused (exit 0): "Ninguna transaccion coincide con el prefijo de id 'ffffffffffffffff'". PASS.
- Re-attach to a tx that already has evidence: refused ("la transaccion ya tiene un purchase_invoice_evidence_id; elimine o reemplace a traves del flujo de adjuntos"). PASS.
- Input guards: `--business-pct` rejected unless MIXED; `persona_fisica` rejected with the accepted enum set surfaced. Instructive boundaries throughout.

## Notes / friction (not failures)
- `work calculate/verify` require the FULL 64-char id (no prefix), unlike `ledger view`/`export`/`attach` which accept unambiguous prefixes — minor inconsistency.
- Export requires profile `identity.name`+`identity.surnames`; error names the missing fields. After profile edits the revision had to be recalculated (deterministic — same revision id since name/activity-start don't change casilla values).
- 303 1T verify initially blocked on a prior-period (2025 4T) compensacion dependency — correct cross-period safety; resolved legitimately by recording the activity-start date (first period of activity), not by bypass.
