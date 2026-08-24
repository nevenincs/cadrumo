---
tags:
  - '#reference'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:3c756bb8fb40924ce2e7033b65bca8b5cbed85c1c0f15d14aba6d88310b1e12d'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-24-registry-completeness-closure-modelo-036-2025-filing-authority-reference]]"
---
# `registry-completeness-closure` reference: `Modelo 036 source-connectivity participation`

## Summary

Modelo 036 participates in source-connectivity at applicability grade only. Its
accepted `manual_by_design` disposition is grounded by a catalogue-resolved,
revision-scoped official procedure and does not create a Cadrumo filing or export path.

## Decision

Modelo 036 revision `2025-02-03-y-siguientes` is a genuine below-filing source participant, but its disposition is `manual_by_design`, not `connected`. The source is the already-enrolled `profile` resolver: the validated binding `modelo-036-profile-censo-status` selects `censo.status` and supplies the exact bound casilla `decl.event-kind`, whose semantic role is `tipo_evento_censal`.

The manual disposition is deliberate and evidence-bearing. The operator remains authoritative for the censo event; `ProfileSourceResolver` resolves that fact with provenance. Separately, the M036 lifecycle records a declaration that the operator already filed at AEAT Sede or in person, and explicitly forbids a local filing action. Neither the profile path nor the lifecycle record authorizes a producer, export layout, or submission route.

## Exact scope

The source census row is restricted to the law-selected Modelo 036 revision, filing year 2025, and the existing `CensoModeloEventKind.ALTA` selector token. Its two typed destinations are the existing `profile` binding source and the existing `tipo_evento_censal` semantic role. This is intentionally not represented as `AD-HOC`: `Period` rejects `alta`, and substituting `AD-HOC` has no law-selected M036 revision.

The existing registry-side census coordinate was extended from `Period` to `Period | CensoModeloEventKind`; `period_token` is the only new projection and remains consumed by the existing canonical `select_revision` validation. No new coordinate model, selector, resolver, persistence path, CLI handler, or filing capability was introduced.

## Evidence chain

- The official catalogue source `aeat-modelo-036-procedure` is cited by the M036 binding and casilla declarations.
- `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/bindings/0001-profile-censo-status.toml` declares `source = "profile"`, selector `censo.status`, and `censo_event_kind`.
- `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/casillas/cdecl.event-kind__cdecl.vigencia-2025.toml` binds `decl.event-kind` to that declaration and gives it `tipo_evento_censal`.
- `src/cadrumo/application/aggregation/_source_profile.py` is the canonical owner of `BindingSourceKind.PROFILE`; existing live-mesh coverage resolves the M036 enum and provenance.
- `src/cadrumo/application/modelo/_m036_lifecycle.py` records human-filed `alta`, `modificacion`, and `baja` events securely and prohibits local filing.

## Census and gate repair

The accepted disposition is recorded in the source-casilla integration campaign's canonical `census.toml` with exact capabilities, destinations, and re-fetchable grounding. It claims the existing `source_ownership:profile` capability exactly once, removing only that identity from the frozen remaining-source-ownership digest.

During validation, the canonical source-discovery gate exposed a pre-existing inability to inspect the current `_leaf` command-spec helper: its evaluator did not resolve declared defaults, local aliases, `or` fallback, or literal string replacement. The repair is confined to the discovery AST evaluator and proves both an explicit handler and the established fallback handler declaration. It neither imports nor executes command specs and does not change CLI behavior.

## Verification and remaining blockers

Focused Ruff is clean. Isolated M036 event-coordinate and `AD-HOC` substitution mutation tests pass; the source-ownership exact-one proof and its misplaced-owner mutation pass; M036 registry binding/foundation tests pass; and discovery regression tests pass.

The all-capability census check now reaches, but remains blocked by unrelated `remaining-calculation-helpers` digest drift. Full bundled closure is separately blocked because Modelo 303 revision `2023` and Modelo 322 revision `2008-2022` claim filing authority while their deadline-window family remains blocked. This work does not claim a global report, release eligibility, S72, or S11 outcome until those external blockers are repaired and the canonical report can compose.

## Reconsideration

Replace this manual disposition only after an accepted decision names a distinct authoritative M036 source and the existing connected-proof contract validates resolver ownership, encrypted calculation provenance, supported operator reachability, and executable evidence. A future filing artifact remains a separate export-authority decision.
