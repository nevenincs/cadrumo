---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:4905eb192b0defd9860a25e879165c77bc7d6ca89f7cc74f1285d734c255e619'
step_id: 'S33'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Verify official export layout selection, mapped semantic owners, and emitted-byte offsets for every filing-grade revision

## Scope

- `src/cadrumo/application/filing/tests/`

## Description

- Use Vaultspec-RAG to locate the validated authority, filing-export closure composer, canonical `export_draft` renderer, live proof authority, and generated provenance manifest; read each epicentre in full and confirm exact symbols with `rg`.
- Replace the stale hard-coded Modelo 303/390 acceptance harness with one integration gate that derives its filing-grade denominator from `ValidatedRegistryAuthority` and reaches every revision through the canonical law-selection coordinate.
- Consume the canonical live filing proof authority only: a satisfied limb must expose generator semantic-map, render-profile, loader, emitted-payload, and official-offset evidence; a refusal must retain the generic export-owner disposition.
- Add a real empty-live-proof bite proving that a declared layout cannot infer emitted-byte evidence, and an M353 pre-2026 versus successor selection bite proving the source/layout refusal cannot be masked by a later revision.
- Keep exact predecessor plan identifiers out of Python. Retain them only in this execution evidence and the existing owner plans.

## Outcome

The gate derives 66 filing-grade revisions from the validated authority. Every revision remains present in the filing-export report and is either evidence-satisfied or explicitly refused; the current corpus has no satisfied filing-export limb.

`CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES` is empty. Therefore 65 filing-grade revisions are live, owned `production-emission-proof` refusals; Modelo 353's pre-2026 law-selected revision is the separate owned `filing-layout` refusal. No payload, semantic map, coordinate, offset, or success proof was fabricated.

The integration gate passed: `uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/application/filing/tests/test_filing_emitted_byte_acceptance.py` — 3 passed in 37.61s. The scoped lint command `uv run --no-sync ruff check src/cadrumo/application/filing/tests/test_filing_emitted_byte_acceptance.py` reported `All checks passed!`. The feature-scoped `uvx vaultspec-core vault check all --feature registry-completeness-closure --no-hints` reported `All checks passed.`

S33 remains open. It cannot honestly close until a filing-grade revision has a canonical semantic map and render profile, generated provenance, a successful production `export_draft` payload, and real official-offset acceptance. The current zero-proof state and the M353 source/layout gap block that acceptance.

## Notes

No-redeclaration audit: semantic discovery identified one canonical filing chain. Exact `rg` found one definition each for `compose_filing_export_coverage`, `_select_export_layout`, `export_draft`, `_render_export_layout`, `_render_layout`, `LiveFilingExportProofAuthority`, and `canonical_live_filing_export_proof_authority`. No modelo-specific renderer, proof authority, layout selector, or plan-route table was added.

The exact open export successors remain Vault-only: Modelo 038 is `W04.P07.S96`; Modelo 721 is `W04.P07.S97` through `S99`; Modelo 182 is `W04.P07.S100`; Modelo 185 is `W04.P07.S101`; Modelo 187 is `W04.P07.S102`; Modelo 188 is `W04.P07.S103`; Modelo 194 is `W04.P07.S104`; both Modelo 220 eras are `W04.P07.S105`; Modelo 390 2021 is `W04.P07.S106`; Modelo 763 is `W04.P07.S107`; and Modelo 840 is `W04.P07.S108`. These rows remain unchecked and their accepted prerequisites are unchanged.

The initial default test invocation selected only unit tests and correctly reported this integration module as deselected. The final explicit integration command is the validation result above. No data was deleted and the plan checkbox was intentionally not changed.
