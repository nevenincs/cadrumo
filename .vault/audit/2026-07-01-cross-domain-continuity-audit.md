---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` audit: rolling code review

## Scope

- Reviewed W09.P41.S323 changes to `src/aeat/domain/user_profile/_schema.py`, `src/aeat/_data/registry/aeat/user_profile/schema.toml`, and focused user-profile schema tests.
- Checked that the change remains schema-only for attribution-entity socios and does not implement the later `atribucion_member` resolver or M100 cross-profile linkage.
- Checked validation evidence from focused user-profile tests, touched-file ruff, vault plan check, and path-scoped diff check.
- Reviewed W09.P41.S410 changes to `src/aeat/_data/registry/aeat/modelos/202/revisions/2025-y-siguientes/deadline_windows/0003-modelo-202-2025-3p.toml`, `src/aeat/_data/registry/aeat/legal/tax-framework.toml`, `src/aeat/_data/corpus/aeat_official/calendars/files/calendario-contribuyente-2025.pdf`, and `src/aeat/domain/calculations/registry/tests/test_modelo_202_deadline_windows.py`.
- Checked that the 2025 `3P` direct-debit cutoff uses the year-specific AEAT 2025 contributor calendar, not only the general Modelo 202 instructions.
- Checked validation evidence from focused Modelo 202 tests, touched-file ruff, plan check, source-resolution, and corpus fingerprint verification.
- Reviewed W04.P19.S398 changes to `src/aeat/domain/calculations/registry/tests/test_modelo_131_regulatory_floor_predicate.py`.
- Checked that S398 closes on the shipped M131 `C01 -> C02` advisory predicate across all revisions, not on the rolled-back `C01 -> C07` predicate shape.
- Checked validation evidence from focused Modelo 131 registry tests, authority-backed application advisory tests, touched-file ruff, reviewer output, and RAG grounding.
- Reviewed W09.P41.S297 changes to `src/aeat/application/modelo/_calculation_actions.py` and `src/aeat/application/modelo/tests/test_modelo_131_data_base_binding_projection.py`.
- Checked that S297 projects only M131 datos-base fixed-record bindings into liquidation casillas `01` and `02`, preserves the official no-datos-base casilla `04` branch, and does not globally project arbitrary manual fixed-record bindings.
- Checked validation evidence from focused Modelo 131 registry/advisory/application tests, touched-file ruff, reviewer output, and RAG/reference grounding.

## Findings

### w09-p41-s323 | low | no findings

No findings for the attribution-entity socios schema slice.

### w09-p41-s410-source-provenance | low | resolved calendar source provenance gap

Initial review found that the corrected Modelo 202 2025 `3P` direct-debit cutoff cited only `aeat-modelo-202-instructions`, while the `2025-12-17` cutoff is grounded in the year-specific AEAT 2025 contributor calendar. The finding was resolved by adding the `aeat-calendario-contribuyente-2025` source catalogue entry, bundling the official PDF corpus, and adding that source ref to the `modelo-202-2025-3p` deadline window. The bundled corpus was verified at `2206696` bytes with SHA-256 `dfdcae8889ab5fecffa368e235d933676c8a479915e09b107734f8339eed0f50`.

### w04-p19-s398 | low | no findings

No findings for the M131 regulatory-floor predicate regression. The current registry predicate is advisory-only, cites `rd-439-2007:art-110`, uses `implies_nonzero(["01", "02"])`, and keeps the rolled-back `implies_nonzero(["01", "07"])` shape absent. The new test does not overclaim predicate-local `source_refs`; it proves source grounding through revision and verification expectation source refs plus bundled corpus evidence.

### w09-p41-s297 | low | no findings

No findings for the M131 datos-base binding projection bridge. The change is scoped to Modelo 131, keeps explicit casilla inputs authoritative over projected backend values, leaves unrelated fixed-record bindings inert, and preserves liquidation casilla `04` as the no-datos-base computation from casilla `03`.

## Recommendations

No open code changes recommended from these reviews. Keep W09.P41.S307 and W09.P41.S324 as separate implementation steps. Keep the full M131 módulos coefficient-table oracle as future work outside S297 and S398; S297 closes the grounded datos-base binding projection, and S398 closes only the advisory regulatory-floor predicate and evidence guard.
