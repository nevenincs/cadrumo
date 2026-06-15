---
tags:
  - '#audit'
  - '#post-refactor-audit-swarm'
date: '2026-06-15'
modified: '2026-06-15'
related: []
---



# `post-refactor-audit-swarm` audit: `post-refactor structural audit swarm`

## Scope

The seven-axis structural audit swarm (per the swarm-audit-cadence discipline)
run after the documentation-tooling separation, the docs-search passthrough
retirement, and the peer `BindingAggregationOp` registry refactor landed on the
`chore/eliminate-shims` branch. The trigger was the cadence rule's
"major structural refactor touching more than two domain subpackages" plus the
accumulation of more than six commits since the prior swarm. Axes covered:
calculation-engine grounding, persistence-boundary identity, cross-domain
handoffs, export/import fidelity, workflow + CLI surface, selector + binding
drift, and semantic functionality-cluster overlap. Findings below were deduped
across axes and re-verified against `HEAD` before any action, per the
treat-output-as-inventory and re-read-HEAD rules.

## Findings

### BIND-01 — default-op misclassification after the BindingAggregationOp refactor (MEDIUM, FIXED)

Surfaced on three axes (calculation-engine grounding, export/import fidelity,
selector + binding drift). After the peer refactor replaced the optional raw
`aggregation` field with the `BindingAggregationOp` StrEnum and a per-family
ROWS default resolved by `binding_aggregation_op()`, four sites still branched on
the raw field — `aggregation is None` (taken to mean "row producer") or a direct
comparison against the un-defaulted value. A binding whose op comes from the
family default (rather than an explicit TOML value) was misclassified: a
row-producing binding could be treated as a scalar and vice versa, silently
dropping or mis-shaping rows on the export and calc-sheets paths.

Pathways and sites: `src/aeat/application/calculations/_row_set_assembly.py:176`
and `src/aeat/application/storage/calc_sheets/_engine.py:951` (both compared the
raw field; now `binding_aggregation_op(binding) != BindingAggregationOp.ROWS`),
`src/aeat/domain/calculations/registry/_export.py:158` (dropped the
`aggregation is None or` short-circuit), and
`src/aeat/domain/calculations/registry/_validate_exports.py:112` (dropped the
`aggregation is not None and` guard). **Disposition: FIXED** (commit `ecfa7b1c4`,
FIX A) with new regression
`src/aeat/application/calculations/tests/test_row_producer_default_op_detection.py`
asserting a default-op ROWS binding is detected as a row producer.

### CLI-DEAD-CITATION-1 / -2 — operator strings cite retired CLI verbs (MEDIUM, FIXED)

Workflow + CLI-surface axis. Operator-facing strings cited CLI verbs that no
longer exist after the config-surface rename: `aeat config doctor` (now
`aeat config check`) and `aeat config profile use <name>` (now
`aeat config switch <name>`). These live outside the conformance gate's reach
(suggestion/default/docstring/locale text), so they were dead instructions a
documented-command sweep cannot catch — the exact fail-open class the
pull-and-file CLI rule warns about for verb renames.

Sites: `src/aeat/entrypoints/cli/_config/_capabilities_cli.py` no-active-profile
default, `src/aeat/application/provisioning.py` (module docstring "the doctor" →
"the check surface" and the `` ``aeat config doctor`` `` reference →
`` ``aeat config check`` ``), and the `cli.config.profile.capabilities.no_active_profile`
Catalan leaf in `src/aeat/locales/ca.yml`. **Disposition: FIXED** (commit
`939f61067`, FIX B; the locale leaf updated through `python -m aeat.locales set`
per the locales-CLI authority rule, not by hand-editing the YAML).

### RECONCILE-DUP — dead parallel reconciler + false "composes" docstrings (HIGH, split disposition)

Semantic functionality-cluster overlap axis. The live modelo reconcile service
`src/aeat/application/modelo/_reconcile.py` reimplements the metadata-level
comparison (modelo, period, `ejercicio`, tax id) inline, but three of its
docstrings claimed it "composes" the low-level reconciler in
`aeat.application.filing.reconciliation._reconcile`. It imports nothing from
there. The `filing.reconciliation` package is a dead parallel reconciler with
zero live importers.

**Disposition: docstrings FIXED** (commit `d87c12129`, FIX C) — the three false
"composes" claims corrected to state the inline reimplementation, and a stale
"per-casilla" diff description corrected to header-field-only. **The dead-package
deletion is DEFERRED as a tracked follow-up:** it is entangled with the registry
"reconciliation" surface consumer link (asserted by `test_modelo_100_registry.py`
and referenced by `test_period_combined_string_gate.py`), so deleting
`application/filing/reconciliation/` requires repointing or retiring that
registry link in the same atomic change. Best done once the peer registry churn
settles; until then the docstring correction removes the false-composition
hazard.

### TERM-SEED-RT — terminology round-trip omits three optional fields (MEDIUM, FIXED)

Persistence-boundary identity axis. The terminology serialise→load round-trip
fixture (`_CURATED` in `dev/docs/terminology_handbook/tests/test_scaffold.py`)
leaves `seed_provenance`, a term's `grammatical_gender`, and `replaced_by` at
their defaults, so a serialise-drops-field / load-re-defaults-field regression on
any of the three was invisible — the anti-default roundtrip-discipline gap.
**Disposition: FIXED** (commit `f7ed1bd84`, FIX D) — a deprecated-concept fixture
populating all three non-default plus a round-trip asserting strict equality,
with guard assertions so the fixture cannot go vacuous.

### EXP-EVIDENCE-01 — export evidence parity surface (MEDIUM, DOCUMENTED)

Export/import fidelity axis flagged the ledger-derived export evidence surface as
worth a parity re-confirmation against the bundled-evidence rule after the
calc-sheets engine touched the row-producer path (BIND-01). Re-verified against
`HEAD`: the bundled-evidence invariant and the offline-vs-Sheets parity gate
(`modelo-export-mirrors-official-structure`) remain in force and green; BIND-01's
fix restores correct row shaping that the parity gate exercises. No code defect
distinct from BIND-01 was confirmed. **Disposition: DOCUMENTED** — no separate
action; tracked here so a future swarm does not re-discover it cold.

### LOW findings (deferred, recorded as inventory)

- **XDH-1 / XDH-2** (cross-domain handoffs): minor handoff-surface observations
  with no confirmed data-loss pathway against `HEAD`. Recorded for the next
  cadence pass; not actioned this cycle.
- **STR-COERCE** (calculation grounding): a `str(...)` coercion of a typed alias
  flagged as a potential type-escape per the boundary-leak rule. Low impact;
  verify whether it sits on a third-party boundary (documentable) or is an
  internal escape (removable) before action.
- **TERM-ANTITAUT**: the terminology round-trip lacked a dedicated
  anti-tautology proof. Partially addressed by FIX D's guard assertions (which
  fail loudly if the fixture goes vacuous); a full mutate-on-disk-then-reload
  proof remains a LOW follow-up.

## Recommendations

- Close the RECONCILE-DUP follow-up by deleting `application/filing/reconciliation/`
  in one atomic commit that also repoints the registry "reconciliation" consumer
  link and updates `test_modelo_100_registry.py` /
  `test_period_combined_string_gate.py` — schedule once the peer registry refactor
  is fully settled.
- Sweep STR-COERCE and XDH-1/2 in the next cadence pass; classify STR-COERCE as
  boundary-documentable or removable.
- Re-run the swarm after the RECONCILE-DUP deletion lands (it crosses a domain
  boundary and removes a package), per the cadence trigger.

## Codification candidates

None this cycle. BIND-01 is a one-time refactor-follow-through, not a recurring
constraint; CLI-DEAD-CITATION is already governed by the
`aeat-cli-pull-and-file-standard` rule (the rename-sweep duty it names is exactly
what was missed and is now restated there); RECONCILE-DUP and TERM-SEED-RT are
covered by the existing `aeat-architecture-boundaries` (no parallel
implementations) and `aeat-roundtrip-discipline` (populate every defaultable
field) rules respectively. No finding surfaced a new cross-session,
constraint-shaped, project-bound lesson the rule set does not already carry.
