---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:18d83f93d176ecf09a623d023d4c1852a3c686c42b863a36ec3548e3989d4524'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-W04-P10-S35]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-11-tui-interface-adr]]"
---
# `casilla-schema` audit: `W04.P10.S35 faceted filtering review`

## Scope

Fresh-context formal review of W04.P10.S35 against the complete casilla-schema plan and execution record, the accepted read-model and TUI-interface ADRs, the canonical review models and closed-axis owners, the transitional TUI screen, focused real encrypted-storage pilots, all four locale catalogues, and facade-promotion commit `ffe78a57a9`.

The review checked total closed-axis coverage, the deliberate omission of single-record lifecycle/progress/verification facets, canonical option ownership, grain-local AND semantics, presence and null semantics, canonical order, exact reset, truthful zero states, localization, narrow-screen behavior, immutable record handling, public-facade imports, repository isolation, prohibited mutation controls, and prohibited test doubles or shortcuts. The accepted TUI curation makes the current inbound-adapter location transitional rather than a new placement finding; later consumer-complete migration remains mandatory.

## Findings

### closed-axis-totality | high | Two honest repeatable casilla axes have no facet

- [ ] The fourteen selectors do not cover every closed axis carried by the repeated casilla grain. `ModeloWorkBindingOrigin.resolved` is a canonical boolean fact but the screen filters only binding source and binding presence. `ModeloWorkRelationConsumption.channels` carries the four closed relation-consumption channels, but the review model widens the canonical registry-owned private `Literal` to `tuple[str, ...]` and the screen exposes only relation presence. Both omissions can distinguish actionable rows without filtering the sole record, so the execution record's totality claim and the P10 exit gate do not hold.

Repair must not hardcode channel strings in the adapter. First promote the existing relation-consumption channel type from its registry owner through the public registry facade, complying with the repository rule that a constant-like closed axis becomes a canonical `StrEnum` in core if required by the architecture boundary; then type `ModeloWorkRelationConsumption.channels` with that public owner and derive the selector directly from it. Add a resolved/unresolved facet over the existing boolean without inventing a domain classification. The omission of lifecycle state, progress state, and verification outcome remains correct: each describes the one record, so those selectors would hide or show the sole record rather than filter a repeatable grain.

### filter-option-localization | medium | Enum choices expose machine tokens and the opened narrow filter panel is unverified

- [ ] `_enum_options` uses each enum value as both the stored value and the visible label. Values such as uppercase filing kinds and long snake-case binding-source tokens therefore remain untranslated operator text in Catalan, English, Spanish, and Hungarian. The four catalogues localize disclosure labels, presence choices, reset, and empty states, but no enum choice labels. The locale pilot never opens the disclosure or inspects any selector option, and the responsive pilot only proves the canonical tables remain usable while the panel starts collapsed. It does not prove the opened controls are readable, focus-traversable, horizontally contained, or reset-reachable at `80x24`.

Keep canonical enum values as Select payloads and order, but render localized labels from catalogue leaves. Add a real pilot that asserts the disclosure starts collapsed, opens it at narrow width in all supported locales, traverses representative first/last controls and a long binding-source option, reaches reset, collapses it again, and retains access to the canonical table.

### facet-gate-bite | medium | The pilots do not independently prove every matcher or conjunction

- [ ] The real pilots exercise each casilla selector on genuine records, preserve canonical order, prove present and absent semantics on the nullable/repeated facts, show truthful zero states, reset exact table row identities, and prove the frozen record is unchanged. However, finding kind and severity are only selected together on a single `blocking_rule`/`blocking` finding and then changed together to a zero-match pair. Ignoring either matcher would still pass. No assertion verifies the intersection produced by two simultaneously active casilla facets, and reset assertions do not verify that all fourteen selector values returned to the public blank state. The option-totality unit test tests `_enum_options` in isolation rather than the mounted selector-to-owner wiring.

Use a real persisted report with findings that vary kind independently from severity, exercise each selector while the other is clear, assert a non-trivial two-facet casilla intersection, and inspect every mounted selector after reset. Perform the production gate-bite required by the campaign: a temporary external runtime mutation or otherwise safe reversible proof must red each independent matcher and the AND composition without modifying tracked production.

## Recommendations

1. Resolve `closed-axis-totality` before closing S35; if canonical relation-channel typing exceeds the adapter-only row, append the prerequisite through the plan intake protocol rather than inventing strings or silently narrowing the exit gate.
2. Resolve `filter-option-localization` with locale-backed display labels whose payload values remain exact canonical enum tokens, plus an opened-panel narrow real pilot.
3. Resolve `facet-gate-bite` with independent real fixtures and a recorded bite proof for every selector, conjunction, reset state, and mounted option owner.
4. Retain the sound boundaries already present: commit `ffe78a57a9` promoted the three shared application types before their consumer; the screen imports no private application module, repository, registry implementation, CLI projection, or persistence adapter; filtering mutates only Textual presentation state and reads the frozen record; row projection is grain-local and canonical-order preserving; zero states are explicit; reset uses public `Select.clear()`; and tests use real encrypted repositories with no fake, mock, stub, patch, monkeypatch, skip, xfail, or mirrored business logic.

## Verification

- Mandatory semantic discovery succeeded for code and vault corpora, then exact declarations, consumers, enum owners, and Git history were confirmed with targeted searches and full-file reads.
- Focused real integration lane: three facet tests passed in 50.97 seconds; nine tests were deliberately deselected and are not claimed.
- The initial pytest attempt selected zero tests because repository unit-lane addopts excluded integration tests; it is recorded as invalid and was rerun correctly with `-m integration`.
- Focused Ruff format and lint: passed.
- Focused strict BasedPyright: zero errors, warnings, or notes.
- Scoped `git diff --check`: passed.
- Locale scaffold check remained red after 48 seconds on the unrelated profile-schema, dependencies-period, retired verification/ledger, and IVA-wallet catalogue debt itemized in the execution record; no S35 filter leaf appeared in the diagnostic.
- Static ownership and prohibited-construct census: no private application import, repository access, record/write mutation, fake, mock, stub, patch, monkeypatch, skip, or xfail in the owned screen and test.

Verdict: **CHANGES REQUESTED / FAIL**. The current implementation is read-only, facade-correct, grain-local, stable, and mechanically green in the bounded lanes, and the deliberate single-record omissions are justified. S35 cannot close while two repeatable closed casilla axes are absent, interactive choice labels remain machine tokens with no opened narrow locale proof, and the pilots do not independently bite every matcher and AND/reset contract.
