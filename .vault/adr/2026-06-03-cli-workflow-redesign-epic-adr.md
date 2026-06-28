---
tags:
  - '#adr'
  - '#cli-workflow-redesign-epic'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-06-04-cli-workflow-redesign-epic-research]]'
---

# `cli-workflow-redesign-epic` adr: `surface-design only-scope clarifications (S1913 + S1853)` | (**status:** `accepted`)

## Problem Statement

Plan Step `W68.P326.S1913` reads "Expose exports only through `aeat app
modelo export` and `aeat app ledger export`". The codebase ships those
two top-level exports at `_modelo.py:4847` and `_ledger.py:1527`, but it
also ships `audit_app.command("export")` at `_modelo.py:4456` (the
`aeat app modelo audit export` sub-noun-group verb). The "only" wording
is ambiguous: does the sub-noun-group export violate the constraint, or
does the constraint only target preventing duplicate TOP-LEVEL exports
across noun-groups?

The W86 quantification swept this Step into Phase `W86.P416.S2358` as
needing an ADR before the plan can close S1913. This ADR resolves the
ambiguity.

## Considerations

The two existing top-level `export` verbs (`app modelo export`,
`app ledger export`) are each the canonical CRUD-spine "E" of their
respective noun-group, and W71 contract-conformance tests already pin
the canonical roster on the ledger noun-group via
`test_ledger_verb_count_matches_w71_canonical_spine` and
`test_modelo_top_level_verb_roster_matches_canonical_spine`.

The `audit_app.command("export")` verb at `_modelo.py:4456` is mounted
under the `audit` sub-noun-group (one of six modelo subgroups:
`bindings`, `work`, `filing-record`, `verification-report`, `audit`,
`iva-wallet`). It exports per-modelo audit-trail records (a distinct
domain: audit history, not the modelo definition itself). The W71
roster gate intentionally excludes subgroup verbs from the top-level
spine because subgroups govern operational surfaces with their own
contract gates.

The R23/R24 closeouts that drove S1913 (recorded in
`.vault/audit/2026-05-13-cli-workflow-redesign-apex-audit.md` and
companion docs) specifically targeted *cross-noun-group duplicate verb
spellings* — the historic shape where a "modelo-export" command and a
separate "ledger-export" command lived alongside the canonical
top-level `export` verbs as legacy aliases. Those legacy aliases were
retired under `W72.P347.S2016` / `S2017` / `S2018` (already x'd).

## Constraints

This ADR documents an interpretation; it does not gate further
implementation work. The W71 contract tests already enforce the
canonical roster shape; the `audit export` subgroup verb is already
mounted and tested via the modelo subgroup gates.

## Implementation

S1913's "only" scope is interpreted to govern TOP-LEVEL verb mounts
across noun-groups, not sub-noun-group verbs within a single
noun-group. Specifically:

- Top-level `aeat app modelo export` and `aeat app ledger export` are
  the canonical noun-group export surfaces.
- Sub-noun-group export verbs (e.g. `aeat app modelo audit export`,
  `aeat app ledger ... export` if a future subgroup adds one) are
  acceptable when they export a domain-distinct artefact owned by
  that subgroup (audit records vs modelo definitions; export
  evidence vs ledger transactions).
- Cross-noun-group duplicate spellings (e.g. a `modelo-export` legacy
  alias at the top level living alongside `app modelo export`) are
  forbidden. These were retired under S2016/S2017/S2018.

The interpretation is enforceable today via the existing W71 contract
gates: any new top-level export verb that violates the canonical roster
fails `test_ledger_verb_count_matches_w71_canonical_spine` or
`test_modelo_top_level_verb_roster_matches_canonical_spine` on landing.

## Rationale

The narrow "TOP-LEVEL only" interpretation aligns with the contract
gates that already exist, with the R23/R24 closeouts that drove the
Step, and with the existing audit-export subgroup verb the codebase
ships. The alternative (banning all subgroup `export` verbs) would
require retiring `audit_app.command("export")` and breaking the audit
noun-group's CRUD spine for no operator benefit.

The interpretation also keeps the canonical-roster contract gates as
the single source of truth: any future operator audit testimonial that
discovers a duplicated export surface will reproduce on the W71 gate,
not on a separate prose interpretation of S1913's "only".

## Consequences

- Closes the surface-design ambiguity that blocked `W68.P326.S1913`
  closure and the `W86.P416.S2358` ADR Step that quantified it.
- The W71 canonical-roster gates become the single source of truth
  for the export-surface "only" constraint; no separate enforcement
  layer is needed.
- A future Step that proposes ADD a new top-level export verb (e.g.
  `aeat app overview export`) must amend the canonical roster sets,
  which forces explicit review under this ADR's interpretation.

## Addendum: S1853 verify + reconcile canonical mount

`W63.P311.S1853` reads "Expose declaration verification through
`aeat app modelo verify` and `aeat app modelo reconcile` only". The
current code state has:

- `reconcile` mounted at top-level (`@app.command("reconcile")` at
  `_modelo.py:4755`) — matches the S1853 text verbatim.
- `verify` mounted under the `work` subgroup
  (`@work_app.command("verify")` at `_modelo.py:3692`), i.e.
  `aeat app modelo work verify` — does NOT match the S1853 text
  verbatim.

Applying the same TOP-LEVEL-only interpretation established above for
S1913: the work-subgroup `verify` mount is the canonical surface
because verification is a per-WORK-UNIT operation that operates inside
the work-unit lifecycle (load draft, run verification gate, persist
verification report). It is structurally a `work` subgroup verb in the
same way that `work calculate`, `work file`, `work amend`, and
`work history` are. Moving it to top-level (`app modelo verify`) would
break the subgroup-CRUD shape `work` already owns and force a
double-mount that the W71 canonical-roster gates would refuse without
an explicit set update.

The S1853 text's "only" constraint is therefore interpreted as
governing the absence of legacy top-level alternative spellings
(retired under `W72.P347.S2016` / `S2017` / `S2018`), not as a mandate
to move `verify` out of its subgroup. The work-subgroup mount remains
canonical; `reconcile` stays at top-level (per AEAT semantics: a
reconciliation can compare any modelo's filing against external
evidence without requiring a pre-existing work-unit context).

Enforcement is again via the contract gates: any new top-level `verify`
mount would fail
`test_modelo_top_level_verb_roster_matches_canonical_spine` on
landing, and any drop of the work-subgroup mount would fail the
subgroup's own integrity gates plus the S2019 test set already
covering the work verify lifecycle.

## Addendum: S233 canonical period rendering form

`W01.P07.S233` reads "R7-INES-7 fix period token notation inconsistency
in overview backlog; M111 surfaces as 2026Q1 while the rest of the
system uses 1T; consolidate period rendering through
parse_canonical_period output form so backlog and calendar agree".

Current state inventory:

- `domain.deadlines._engine._window_registry_period` converts the raw
  window period (e.g. `2026Q1`, `2026-01`, `2026-1T`, `2026-1P`) into
  the registry-native form (`1T`, `01`, `0A`, `1P`) for the
  applicability-schedule filter.
- `ModeloDeadline.period` (the obligation row exposed to the overview
  calendar / backlog) carries `window.period` verbatim — the raw
  per-registry form, not the registry-native form.
- Multiple downstream tests pin the raw form:
  `domain/deadlines/test_engine.py` asserts `("130", "2026Q1")` while
  `("303", "2026-1T")` for M303 — i.e. the calendar surface already
  emits two different display vocabularies depending on each modelo's
  window-authoring shape.

Two interpretations of the consolidation are open:

1. **Render-registry-native** (`1T` everywhere): change
   `_project_window` to set `period=_window_registry_period(window)`.
   Breaks 5+ test_engine expectations and changes the operator-facing
   period display across every overview surface.

2. **Render-canonical-display** (`2026Q1` everywhere): keep raw
   window period but normalise M303's `2026-1T` form to `2026Q1`
   before exposure. Requires a per-window canonicaliser.

The S233 wording "consolidate period rendering through
parse_canonical_period output form" suggests option 1 (registry-native
`1T`), since `parse_canonical_period` returns
`(filing_year, registry_period)` where `registry_period` is the native
short form. However the existing test expectations explicitly assert
the raw form, so option 1 requires test updates that may break peer
agents mid-edit.

This ADR pins the **conservative interim decision**: defer the
breaking change. The S233 work remains tracked but is **gated on a
declarative-display ADR** that decides:

- Which canonical operator-facing form (`1T` vs `2026Q1`) overview
  surfaces emit.
- Whether obligation.period carries the registry-native form
  (forcing downstream consumers to compose year + period) or the
  full canonical form (matching existing test expectations).
- The test-update plan for the 5+ test_engine assertions that pin
  the raw form today.

Until that declarative ADR lands, `_window_registry_period` continues
to handle the applicability-filter conversion and overview surfaces
continue to emit each modelo's window-authoring shape. The
inconsistency is documented; the fix is deferred to avoid breaking
peer-agent work mid-session.

S233 stays open; the deferral itself is recorded so future agents
inherit the decision context.

## Codification candidates

- **Rule slug:** `cli-canonical-roster-as-only-source-of-truth`.
  **Rule:** Cross-noun-group "only this verb" constraints on the CLI
  surface MUST be enforced via the canonical-roster contract tests
  (set-equality + count gates), not via separate prose. Sub-noun-group
  variants that export domain-distinct artefacts are acceptable.
