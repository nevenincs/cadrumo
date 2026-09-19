---
tags:
  - '#research'
  - '#silent-zero-regression-screen'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f93fab95a983006014b329e0ee1749e44abcb5171f6a061f71d6a3523f49f920'
related: []
---

# `silent-zero-regression-screen` research: `detecting a binding whose resolved value silently regresses to zero`

The calculation engine screens one direction of silent under-declaration and not its mirror. `unsupported_ledger_*_observations` (e.g. `unsupported_ledger_iva_observations`, `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:617`) proves an observation nothing consumes is caught: an observation targeting a bogus casilla is flagged 1/1. Measured live on the M130 retenciones binding while evaluating a proposed change, the mirror direction — a binding that used to resolve a non-zero value now resolving zero — passed every existing check:

```
BEFORE: retenciones binding value = 300.00
AFTER:  retenciones binding value = 0
screen: 0 flagged before, 0 flagged after
```

Every income observation stayed routed, so the observation screen was satisfied — true, and irrelevant to whether the retención credit survived. This document grounds why the gap survived (three adjacent mechanisms each miss it for a different reason), evaluates four candidate detection shapes against real cost and false-fire evidence, and names the shape the evidence favors. No ADR governs this asymmetry today; `vaultspec-rag` search (`--type vault`, both directions of the question) surfaced no ruling that the observation-only screen was a deliberate scope decision — `.vault/audit/2026-06-10-calculation-engine-foundations-audit.md` finding F4, which installed the observation screen, discusses only that direction and never considers or rejects the value-regression direction.

## Findings

### Three mechanisms sit adjacent to the gap and each misses it for a different reason

This is a more useful description of the gap than "there is no gate": each mechanism looks, from a distance, like it should cover the case.

1. **The observation screen** (`unsupported_ledger_*_observations`, one per source family, e.g. `_ledger_bindings.py:617`) asks the wrong question for this failure: whether ledger rows are consumed by some binding, never whether the binding's AGGREGATE output is the value it should be. A binding can consume every observation correctly and still sum them to a number nobody would recognise, or sum zero observations because none matched a retargeted selector, and this screen is silent either way.
2. **`expected_but_missing_binding_ids`** (`src/cadrumo/application/modelo/_calculation_source_staging.py:394-431`) asks the right family of question at the wrong granularity: it tests `binding.id in resolved_binding_values`, which is `True` whether the mapped value is `Decimal("300.00")` or `Decimal("0")`. It exists to catch a present source that resolved literally NO entry (total resolver silence), a different and narrower failure than "resolved an entry, and the entry is a wrong zero." The M130 BEFORE/AFTER probe above tripped neither this gate nor the observation screen, and this is the near-miss the original measurement did not distinguish from the first.
3. **`implies_nonzero(["antecedent_id", "consequent_id"])`** (`src/cadrumo/application/modelo/_verification_predicates.py`, evaluator `_advisory_implies_nonzero_fires` at line 619) is the right SHAPE — a declared antecedent-nonzero implies consequent-nonzero material implication, the mechanism behind the `no-silent-under-declaration` rule's M200 worked example (`.vault/adr/2026-06-02-modelo-200-base-determination-adr.md`) — but it fires at VERIFY time, not calculate time, and is opt-in per casilla pair: an author must declare the antecedent/consequent for a specific casilla in the registry TOML. Nobody has authored one for the M130 retenciones casilla, so the mechanism that would catch this class exists and simply was never pointed at this binding.

None of the three is a live gate for the measured case today, and none is a natural "extend this one file" fix: (1) and (2) answer different questions structurally; (3) answers the right question but requires per-casilla authorship this instance never received.

### Four candidate detection shapes

Each is evaluated on what it catches, what it misses, its authoring/runtime cost, and — weighted most heavily, per the project's own standing lesson that an advisory firing on correct filings forfeits every true positive (`ledger-iva-advisory-only-on-cuota-bearing-categories`) — how it could false-fire.

**1. Calculate-time comparison against the prior period/revision.**
Catches the exact measured regression: any binding whose resolved value drops from a real prior figure to zero. Misses a first-ever filing (no prior period exists to compare against — unguardable by construction) and misses a regression that changes a nonzero value to a DIFFERENT nonzero value (a wrong-but-non-zero silent corruption, arguably worse, entirely outside this shape's detection surface). Cost is real: no existing helper loads "the prior calculation revision for this modelo/taxpayer" generically at calculate time for comparison purposes — `previous_filing` binding resolution (`domain/calculations/registry/_bindings_previous_filing.py`) is a narrow, source-specific mechanism that populates ONE casilla's value from a prior filing as a calculation INPUT, not a general diff-against-prior primitive; this shape needs new state-loading machinery. False-fire risk is HIGH and structural rather than incidental: a taxpayer legitimately has zero retenciones after a nonzero prior quarter constantly (a client stopped paying, a contract ended, a one-off withholding event), and every one of those legitimate transitions fires the same advisory as a real regression — the exact shape the cuota-less-categories rule was written to prevent recurring.

**2. Registry-build reachability.**
Asserts every declared ledger-backed binding CAN match at least one constructible observation shape, at registry-build time, with no runtime taxpayer state. Catches the measured failure directly and before any run: the retarget that zeroed M130 retenciones would have failed build the moment the binding's selector stopped matching any constructible row shape. Structurally cannot catch a binding that is correctly wired (reaches real matching rows) but has a runtime logic bug computing the aggregate wrong — the "reaches something and computes it wrong" case is outside every shape considered here, not only this one. Cost is real but scoped: each binding source family already declares a typed selector (`BindingSourceKind` plus the per-family selector model, `binding-validation-single-contract`), so a per-family reachability probe (construct a synthetic minimal matching row, assert `resolve()` accepts it) is buildable per family rather than as one universal function; roughly 7+ source-kind families (per `.vault/audit/2026-06-10-calculation-engine-foundations-audit.md` F4's estimate of the enrolled-source surface) would each need an independently-authored probe, hung on the existing per-family module seam (`registry-resolver-family-extraction`). False-fire risk is LOW by construction: the check runs against the registry's own declared shape at build time, never against a taxpayer's actual filing data, so a legitimately-zero filing cannot trigger it at all; its only false-fire mode is a bug in the reachability probe's own judgment of what is constructible, a one-time per-family authoring risk rather than a per-taxpayer noise risk.

**3. Golden-value regression (a pinned, grounded representative filing).**
Catches exactly the scenario a proposed change breaks, if that scenario is among the pinned fixtures. Misses everything outside the fixture set — coverage scales with authored fixtures, not with the registry's actual binding surface, the weakest of the four on that axis. Cost is cheap to start (one fixture) and expensive to reach meaningful coverage (one grounded fixture per binding family worth protecting, comparable order of authoring cost to option 2's per-family probes) — and the fixture must be externally grounded (AEAT worked example or workbook), never hand-computed from the same formula under test, per `no-tautological-calculation-tests`; this project has already paid for a variant of this mistake once (a duplication-measurement tool that built the same duplication it measured). False-fire risk is LOW for the pinned scenario itself (fixed input, fixed expected output) but MEDIUM in maintenance: a legitimate formula change requires re-grounding every affected fixture, and a fixture re-grounded by bumping it to match new code output rather than re-deriving from the external oracle silently becomes tautological — invisible until someone checks it against the oracle again.

**4. Generalise `implies_nonzero` from opt-in to a build-time-enforced floor.**
Not one of the three originally posed; follows directly from finding that mechanism 3 above (`implies_nonzero`) is the right shape already built but never required. Registry-build would assert that every casilla whose binding source is ledger-backed (excluding `previous_filing`/`relation_prefill`/`manual_input`, mirroring the `non_silent_sources` exclusion already declared in `expected_but_missing_binding_ids`) either names a `verification_predicate` in which it appears as a consequent, or is listed on an explicit can-legitimately-be-zero exemption set — mirroring `CUOTA_LESS_M303_IVA_CATEGORIES` (`src/cadrumo/domain/iva/_schema.py:190`), the project's own established pattern for a reasoned, named, auditable zero-is-fine carve-out. This does not invent a new detection mechanism; it converts an existing one's coverage from "someone remembered to author a predicate" into "the build requires an author to have made an explicit choice, guard or exemption, for every casilla in scope." It would not have caught the M130 case directly (no predicate had been authored for that casilla, so this shape's own gate would already have been failing at build time before the incident — which is arguably the more useful finding: the casilla was already out of compliance with a floor that does not yet exist). Cost is lower than option 2 (reuses existing predicate infrastructure and evaluator, adds only the build-time completeness sweep and the exemption-set authoring for genuinely-can-be-zero casillas) but weaker in what it independently detects, since it still depends on the AUTHORED predicate's antecedent being the right one — an author could satisfy the floor with a technically-true but weak predicate. False-fire risk is LOW-to-MEDIUM: LOW for the completeness sweep itself (build-time, no taxpayer data), but the predicates it forces into existence inherit whatever false-fire profile their authored antecedent carries — a poorly-chosen antecedent could reintroduce option 1's noise risk one casilla at a time, so this shape's overall safety depends on predicate-authoring discipline, not on the mechanism alone.

### What no shape here catches

Option 2 (and, by inheritance, option 4's structural half) catches "the binding cannot reach anything" and structurally cannot catch "the binding reaches something and computes it wrong" — a resolver correctly wired to real matching rows that aggregates them incorrectly. This wrong-but-nonzero case is arguably worse than a visible zero (it looks plausible) and is outside every shape evaluated in this document. Naming this here rather than implying full coverage is deliberate.

### What was not investigated

Whether a cheaper approximation of option 1's prior-period comparison — scoped only to casillas already carrying an `implies_nonzero` predicate authored elsewhere, or gated behind an explicit "this casilla is structurally continuous" registry flag — would narrow its false-fire surface enough to be viable. This is a hybrid of options 1 and 4 that was not modelled quantitatively; it is named here as a possible fifth shape for a future pass rather than evaluated, since doing so would require the same prior-revision state-loading machinery option 1 needs before any false-fire measurement could be taken.

## Sources

- `src/cadrumo/domain/calculations/registry/_ledger_bindings.py:617` — `unsupported_ledger_iva_observations`, the observation-consumption screen.
- `src/cadrumo/application/modelo/_calculation_source_staging.py:394-431` — `expected_but_missing_binding_ids`.
- `src/cadrumo/application/modelo/_verification_predicates.py:59,619` — the `implies_nonzero` predicate pattern and its evaluator `_advisory_implies_nonzero_fires`.
- `.vault/adr/2026-06-02-modelo-200-base-determination-adr.md` — the `no-silent-under-declaration` worked example using `implies_nonzero`.
- `.vault/audit/2026-06-10-calculation-engine-foundations-audit.md` — finding F4, the observation-screen's own origin and estimated enrolled-source-family scale (7+ kinds).
- `src/cadrumo/domain/iva/_schema.py:190` — `CUOTA_LESS_M303_IVA_CATEGORIES`, the reasoned-exemption-set pattern option 4 mirrors.
- `src/cadrumo/domain/calculations/registry/_bindings_previous_filing.py` — the narrow, source-specific `previous_filing` mechanism, cited as evidence that no generic prior-revision comparison primitive exists today.

## Context

Measured during a session-long registry-hardening pass alongside two unrelated corrections to stale governing documents (the `modelo-locales-cli-authority` rule and the `2026-05-01-corpus-data-hydration-adr`), both surfaced by accident while doing something else — the session's own recurring shape: a decision or a gap living somewhere a later reader did not look.
