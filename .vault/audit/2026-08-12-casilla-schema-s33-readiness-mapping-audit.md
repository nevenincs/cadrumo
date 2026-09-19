---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:a9739b6fb1da72e4a474753f877134b66b35620bcd34c4ccf93ff6a3ec4b4879'
related:
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-plan]]"
---
# `casilla-schema` audit: `S33 readiness mapping review`

## Scope

Reviewed S33 against the accepted dead-surface and blocker-spine decisions, the application projection, every CLI consumer, direct tests, four locale catalogues, the S33 execution record, and bounded static/catalogue gates.

## Findings

### locale-authority-drift | high | Readiness leaves fail the mandatory locale scaffold gate

`python -m dev.locales scaffold --check` reports every one of the 21 new `cli.app.modelo.bindings.readiness.*` leaves as extra in all four catalogues. The application mapping stores locale keys as ordinary string values, so the catalogue authority's code-key discovery does not recognize them as live `tr()` leaves. The same run also reports unrelated shared-worktree drift, but the 21 readiness extras are owned by S33. The current tree therefore cannot satisfy stale-key parity or the `dev.locales` contract, and the execution record's verification claim is false for the present implementation.

### incomplete-behavioural-proof | medium | Tests validate the table but not the CLI behaviour or semantic grouping

The added test imports the production mapping, compares its keys with the production enum, loops over the mapping's own values, and checks immutability. Those assertions enforce totality and leaf resolution without a hard enum count, but they do not exercise the list and resolve CLI paths, prove that an unknown source fails closed at the consumer, or independently anchor the intended shared-ledger grouping versus distinct-source nouns. A wrong but total production mapping can satisfy the test. Add real CLI-output coverage and explicit semantic anchors derived from the accepted source taxonomy, without mirroring the entire mapping.

### execution-record-overclaim | medium | S33 records gates as passed despite a current red authority gate

The S33 execution record says readiness leaves were authored through `dev.locales set-batch` and that verification passed. The authoritative `dev.locales scaffold --check` gate is red specifically on all new readiness leaves, so the record does not truthfully describe the current tree. Keep S33 open until the catalogue discovery shape is supported, the authority gate is green for the S33 surface, and focused CLI behaviour tests pass.

## Recommendations

- Make the application-owned locale-key projection visible to the `dev.locales` authority without restoring an entrypoint dictionary, fallback, alias, or duplicate semantic mapping.
- Add real list and resolve CLI assertions plus independent anchors for the deliberate shared ledger noun and representative distinct sources.
- Re-run `dev.locales scaffold --check`, catalogue audit/honesty tests, focused readiness tests, Ruff, typing, and `git diff --check`; then update the execution record with exact current evidence.

The production shape itself is otherwise aligned: the legacy dict/helper is deleted; the Spanish-named `MappingProxyType` is keyed by `BindingSourceKind`; import-time exact set equality is enforced; all three CLI consumers use typed indexing followed by `tr()` with no fallback/default; and Ruff passes on the changed Python surface. No authored English alias for the tax stem was found; English and Hungarian both carry the Spanish stem, so no doubled-stem drift was introduced.

## Re-review resolution

### locale-authority-drift | resolved | Scanner-visible canonical mapping closes S33 readiness drift

The canonical application owner is now `CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS`. Its `_LOCALE_KEYS` suffix admits the mapping's literal values to the repository AST scanner without adding a second key inventory. `python -m dev.locales scaffold --check` remains globally red on concurrent profile-schema, IVA-wallet, retired-verification, dependency-help, and ledger catalogue work, but reports zero missing or extra `cli.app.modelo.bindings.readiness.*` leaves. The S33-owned high finding is closed with an honest unrelated-drift boundary.

### incomplete-behavioural-proof | resolved | Real list and resolve commands anchor distinct Spanish nouns

The added registry-surface integration test invokes the actual Spanish JSON `bindings list` path for Modelo 200 and `bindings resolve` path for Modelo 303. Registry-produced `relation_prefill` rows render `entrada de relaciÃƒÂ³n`; registry-produced `ledger_iva_aggregation` rows render `datos del libro`. This is behavior-level evidence across both consumers, not a mirrored copy of the complete mapping. The property tests continue to enforce enum-relative totality, all-catalogue resolution, and immutability without a hard member count.

### execution-record-overclaim | resolved | Execution evidence now states the exact locale boundary

The S33 record names the scanner contract and real CLI regression, records nine focused passes, and explicitly says the locale scaffold is red only outside S33 while no readiness leaf is missing or extra. Its claims match the current bounded review.

## Re-review verification

- Focused projection plus real CLI integration lane: 9 passed in 10.76 seconds.
- Ruff over the application owner, CLI consumer, and two direct test modules: passed.
- BasedPyright over the application owner and direct projection test: zero errors, warnings, or notes.
- Scoped `git diff --check`: passed.
- Exact-symbol sweep: the old entrypoint dict and fallback helper remain absent; all three consumers index the typed application mapping and call `tr()` without a default.
- Manual semantic review: ledger-backed kinds deliberately share `datos_libro`; retention, IVA compensation, regularisation, invoice, evidence, foreign-asset, related-party, attribution, refund, and donor sources retain distinct nouns. No new English alias for the tax stem and no doubled-stem wording was authored.

## Re-review verdict

S33 is ready within its owned surface. All three original findings are resolved. The remaining locale scaffold failures belong to concurrent non-S33 work and are recorded as an explicit full-tree validation boundary, not treated as green.
