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

### RECONCILE-DUP — dead parallel reconciler + false "composes" docstrings (HIGH, FIXED)

Semantic functionality-cluster overlap axis. The live modelo reconcile service
`src/aeat/application/modelo/_reconcile.py` reimplements the metadata-level
comparison (modelo, period, `ejercicio`, tax id) inline, but three of its
docstrings claimed it "composes" the low-level reconciler in
`aeat.application.filing.reconciliation._reconcile`. It imports nothing from
there. The `filing.reconciliation` package was a dead parallel reconciler with
zero live importers — a design-only implementation shell (it did field-by-field
justificante comparison but was never wired to any CLI verb), which
`aeat-source-hygiene` forbids.

A vaultspec-rag semantic sweep of the reconcile cluster (queried by behaviour,
not symbol) confirmed exactly two production reconcile sites — this dead package
and the live, CLI-wired `application.modelo._reconcile` — with no hidden third
site. A symbol-level grep confirmed the dead package's public API
(`ReconciliationReport`, `ReconciliationStatus`, `ModeloDivergenceKind`,
`ModeloDraftRef`, `JustificanteRefSummary`, `reconcile`) had zero external
importers.

**Disposition: FULLY FIXED.** Step 1 — docstrings corrected (commit `d87c12129`,
FIX C): the three false "composes" claims now state the inline reimplementation,
and a stale "per-casilla" diff description was corrected to header-field-only.
Step 2 — the dead package was **deleted** and the registry
`modelo-100-reconciliation` application-link `consumer` repointed from
`aeat.application.filing.reconciliation` to the live
`aeat.application.modelo.modelo_reconcile`; the `test_modelo_100_registry`
application-links assertion was updated to match, the now-dead
`test_period_combined_string_gate` allowlist entry for the deleted reconcile test
was removed, the stale sanitizer no-write-test comment was de-referenced, and the
4 orphan `docs/api` stubs were removed via `apidocs scaffold` (drift check clean).
This change set landed coherently at `HEAD` (swept into commit `fe474ff1d` by the
shared-worktree auto-commit process; verified piece-by-piece at `HEAD` — package
gone, consumer repointed, assertion updated, allowlist entry removed, stubs gone,
filing toctree clean). Gates green: registry application-links test, period gate,
modelo reconcile tests, layout import smoke, sanitizer no-write test; 794 tests
collect with no import breakage.

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

### LOW findings (all closed)

- **TERM-ANTITAUT** — **FIXED** (commit `88944e574`). A dedicated anti-tautology
  proof was added to the terminology round-trip: a value mutation on the
  serialised TOML surfaces as strict inequality on reload, and dropping the
  required `[concept]` table makes the loader raise `TerminologyValidationError`
  rather than silently re-default. The round-trip suite is no longer vacuous.
- **STR-COERCE** (calculation grounding) — **VERIFIED NON-ACTIONABLE**. The
  flagged `str(...)` sites were re-examined at `HEAD`: every production hit is a
  legitimate rendering, not a typed-alias type-escape. `str(obs.value)` /
  `str(row.value)` / `str(entry.value)` coerce a `Decimal | str | None` *union*
  field (a real string projection for JSON/CLI). `str(period)` invokes
  `Period.__str__` — `Period` is a pydantic `BaseModel`, not a `str` subtype, so
  the call formats the AEAT token (explicitly documented as the "human-readable
  `str(period)` form" in `domain/filing/_schema.py`), not a no-op coercion. No
  bare `str()` erasing an already-`str` StrEnum/alias was found. The boundary-leak
  rule is not violated; nothing to remove or document inline.
- **XDH-1 / XDH-2** (cross-domain handoffs) — **VERIFIED NON-ACTIONABLE**. The
  calculation→persist→export provenance handoff carries `legal_refs` /
  `source_refs` through typed envelopes and is guarded at `HEAD` by multiple
  roundtrip/conformance tests (`test_json_envelope_roundtrip`,
  `test_calc_sheets_apply_evidence`, the offline-vs-online calc-sheets
  conformance test, filing runtime). No data-loss pathway was reproducible; the
  observations were soft and are closed without a code change.

## Recommendations

All findings from this swarm are now closed — every MEDIUM/HIGH item fixed and
verified, every LOW item fixed or verified non-actionable. Remaining standing
guidance:

- **Re-run the swarm** at the next cadence trigger: the RECONCILE-DUP package
  deletion crossed a domain boundary and removed a package, which is itself a
  cadence trigger; the next pass should re-confirm no dangling references to the
  removed `application.filing.reconciliation` surface remain.
- Watch the docs API-stub tree: the shared worktree accrues peer-module stub
  drift (e.g. the `_decimal_binding_value`→`_decimal_parsing` rename observed
  during this pass); a periodic `apidocs scaffold` keeps the nitpicky docs build
  green. This is worktree hygiene, not a finding.

## Codification candidates

None this cycle. BIND-01 is a one-time refactor-follow-through, not a recurring
constraint; CLI-DEAD-CITATION is already governed by the
`aeat-cli-pull-and-file-standard` rule (the rename-sweep duty it names is exactly
what was missed and is now restated there); RECONCILE-DUP and TERM-SEED-RT are
covered by the existing `aeat-architecture-boundaries` (no parallel
implementations) and `aeat-roundtrip-discipline` (populate every defaultable
field) rules respectively. No finding surfaced a new cross-session,
constraint-shaped, project-bound lesson the rule set does not already carry.
