---
tags:
  - '#research'
  - '#transient-state-hardcoding'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - '[[2026-07-27-transient-state-hardcoding-adr]]'
---
# `transient-state-hardcoding` research: `hardcoded transient-state inventory`

Which checked-in numbers in this tree encode transient state - a measurement of
what the tree happens to contain at some HEAD - rather than an invariant fixed
by an authority outside the tree? Inventory measured at HEAD `d1e91cb00f2d` on
2026-07-27. The evidence picture: two rot mechanisms operate (unguarded pins
drift silently; zero-slack pins stay true but are substitution-blind and
serialize concurrent writers), a census-pin population survives in gate tests,
and sound identity-keyed patterns already ship in this tree for the defective
sites to converge on.

## Findings

### Method

The semantic code index is truncated while reporting itself healthy (dispatch
brief: ~1027 chunks against ~4546 files, empty `degraded_reasons`), so no claim
below rests on semantic search. Every site was established by `rg` pattern
sweeps plus whole-file reads:

- `assert len(...) == N` over `src/**/test_*.py` (first 120 hits reviewed;
  fixture-derived hits excluded by reading context).
- `== \d{1,4}` word-bounded, over `src/cadrumo/tests/` (full result set).
- `BASELINE|RATCHET|_FLOOR|_CEILING|ratchet` over `src/**/*.py` (108 files;
  the gate-bearing ones read).
- Conventionally-named integer constants (`MAX_*`/`MIN_*`/`*_CEILING* = <int>`)
  over `src/cadrumo`.
- `dev/*.json` checked-in baselines parsed and read.
- Whole-context reads of `src/cadrumo/tests/test_lazy_import_policy.py`,
  `src/cadrumo/tests/test_import_hygiene_gate.py`,
  `src/cadrumo/tests/_size_budget.py`, and each census-assert site below.

Scope: production source and gate tests under `src/cadrumo/`, checked-in
baselines under `dev/`. Deliberately not swept: `.vault/` record prose (a
concurrent consistency sweep owns those corrections; its output had not landed
under `.vault/audit/` at measurement time), `docs/` prose, registry TOML
interiors, `dev/docs` tooling, `.seq` fixtures. Every count in this document is
a dated observation anchored to the HEAD above.

### Two rot mechanisms, both evidenced in-tree

Unguarded pins drift silently. The size-budget gate's per-module and
per-callable override pins, many commented as "no headroom", accumulated 8901
lines of aggregate positive slack (measured by the harness-honesty audit cited
under Sources, finding `stale-size-budget-pins-permit-silent-regrowth`; worst
confirmed offender: the overview calendar module pinned at 1667 against an
actual 947). The lazy-import gate's own comment records the same failure in its
past: its ceilings "drifted to 84 sites of dead headroom" before the zero-slack
companion was added (`src/cadrumo/tests/test_lazy_import_policy.py:838-840`).

Zero-slack pins do not drift but are substitution-blind and serialize writers.
`test_ceilings_carry_no_slack_over_the_live_counts`
(`src/cadrumo/tests/test_lazy_import_policy.py:1156`) pins every ceiling AT its
live count, so staleness fails loudly - but a count cannot distinguish
{A, B, C} from {A, B, D}: one site added plus one removed in the same class is
green with no review. And because every addition edits the same integer line,
two concurrent authors always conflict, and a mis-resolved merge of two
independent increments silently mis-sets the ceiling.

Prose beside a pin rots even when the pin is maintained.
`src/cadrumo/domain/usage_ratios/tests/test_model.py:119` says "The count pin
(twelve)" while the assertion at line 128 says 15 - the number was maintained,
the sentence was not.

### T1 - census counts redundant beside an identity assertion in the same test

Each site asserts a count in a test that already carries the stronger identity
assertion; the count adds nothing the identity does not, and goes stale on
every legitimate change.

- `src/cadrumo/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py:186`
  - `len(LEDGER_BINDING_SOURCE_KINDS) == 7` immediately after lines 176-184
  assert the seven-member identity set. The docstring also narrates ordinals
  ("the sixth is...", "the seventh is...").
- `src/cadrumo/domain/usage_ratios/tests/test_model.py:128` -
  `len(ELIGIBLE_USAGE_RATIO_CATEGORIES) == 15` after line 127 asserts equality
  with the registry-derived frozenset (plus the stale "twelve" prose above).
- `src/cadrumo/domain/portals/tests/test_registry.py:71-73` -
  `test_registry_count_is_41`, while lines 66-68
  (`test_registry_closure_over_portal_enum`) assert
  `set(PORTAL_REGISTRY.keys()) == set(Portal)`.
- `src/cadrumo/tests/test_modelo_authorization_gate.py:157` -
  `assert FLEET_SIZE == 73` after lines 155-156 tie `FLEET_SIZE` to the fleet
  tuple. Production already derives it: `FLEET_SIZE = len(CANONICAL_MODELO_FLEET)`
  (`src/cadrumo/core/access_gate/_authorization.py:74-78`), and an accidental
  `Modelo` enum edit is separately caught by the enum-to-registry parity gate
  (`src/cadrumo/core/tests/test_modelo.py`). The docstring narrates count
  history ("became 73 when Modelo 145 was added").

### T2 - census counts pinned as deliberate-change tripwires, no identity companion

These pins exist to force a human re-look when a registry or corpus set changes
(one documents that intent explicitly). They fire on any cardinality change but
cannot name the change and cannot see a substitution.

- `src/cadrumo/tests/test_registry_locale_key_parity.py:96` -
  `len(keys) == 86`; the docstring (lines 91-93) states the pin is deliberate.
  The carve-out invariant actually protected is line 97 (no `.quote` keys),
  asserted independently.
- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py:252`
  - `len(definitions) == 67`; the test name (`test_all_67_namespace_rows...`,
  line 249) encodes the census too. The structural `all(...)` assertions that
  follow are the real invariant.
- `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py:252`
  - `len(checked) == 18` closing a loop over the bundled Modelo-100 corpus
  manifest (anti-vacuity is the residual value; the count also pins the
  title-filter skip behaviour of lines 234-239).
- `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_normatives.py:523`
  - `len(checked) == 51`, with a hand-derivation comment (lines 514-522)
  reproducing the arithmetic (28 + 10 + 13) and the retired prior value (72).
- `src/cadrumo/domain/portals/tests/test_registry.py:182` and `:196` -
  `len(mapping) == 41`; lines 186-187 additionally assert the literal log text
  "loaded 41 portal entries" (the production message interpolates the count;
  the test hardcodes it).
- `src/cadrumo/domain/portals/tests/test_smoke.py:30` -
  `len(PORTAL_REGISTRY) == 41`.
- `src/cadrumo/tests/test_hardcoded_constants_inventory.py:191` -
  `len(_PATTERN_CONTROLS) == 5` ("every scan pattern in this module needs a
  control pair") - an intra-module parity claim expressible as key-set equality
  against the patterns the module declares.

### T3 - checked-in ratchet counters under a zero-slack pin

`src/cadrumo/tests/test_lazy_import_policy.py:843-853` declares
`_SITE_CEILINGS`: ERROR_REGISTRY_BOOTSTRAP 4, NAMED_CYCLE_BREAK 1,
PORTS_INVERSION_PENDING 0, DOMAIN_CYCLE_BREAK 50, ADAPTER_INTERNAL_DEFERRAL
168, CORE_INTERNAL_DEFERRAL 37, APPLICATION_DEFERRAL 527; line 872 declares
`_ALLOWLIST_EDGE_CEILING = 482`. The zero-slack companion (line 1156) makes
them live tree measurements by construction. The identity data sits beside
them: `_ALLOWLIST` enumerates the edges as `ImportEdge(consumer, target)`
pairs. Residual value the edge set alone lacks: several SITES can share one
EDGE (lines 833-835), so a new function-local import on an already-allowlisted
edge is visible only to the count. Precedent for excluding volatile coordinates
from site identity: `_BaselineSite` excludes `lineno` from equality
(`src/cadrumo/tests/test_import_hygiene_gate.py:108-119`).

### T4 - pins with unguarded slack

`src/cadrumo/tests/_size_budget.py` per-module and per-callable override pins
(drift measured above). The machinery for the sound form already exists in the
same module: tolerance bands (`default_limit`, `headroom_ratio`, `slack_ratio`,
`slack_floor`, lines 117-129) and a stale-budget detector exercised by
`src/cadrumo/tests/test_codebase_size_budgets.py:193,205`.

### Sound patterns already in-tree (convergence targets)

- Identity-keyed baseline with two-sided equality:
  `dev/import_hygiene_baseline.json` and `dev/import_hygiene_test_debt.json` -
  named, reasoned entries; the gate asserts both count-not-exceeded and
  named-set equality, with counts derived from the lists
  (`src/cadrumo/tests/test_import_hygiene_gate.py:15-48`). Same shape:
  `src/cadrumo/locales/_intentional_identical.json` (locale honesty ratchet,
  reasoned entries).
- Derived production constant: `FLEET_SIZE = len(CANONICAL_MODELO_FLEET)`
  (`src/cadrumo/core/access_gate/_authorization.py:76-78`), commented "derived
  from the canonical fleet rather than hard-coded so the two cannot disagree".
- Registry-derived closure: `src/cadrumo/domain/usage_ratios/tests/test_model.py:121-127`
  re-derives the eligible category set from the registry and asserts equality -
  stale-proof by construction (the trailing count pin is the defect, not the
  closure).
- Anti-vacuity floors with declared, deliberate slack:
  `MIN_SCANNED_MODULES = 2000` and `MIN_SCANNED_CALLABLES = 7500`
  (`src/cadrumo/tests/_size_budget.py:75-81`) against a measured population of
  9933 production callables - order-of-magnitude scanner-health bounds, not
  tree pins.

### Numbers established as NOT transient (grounded)

- Format and crypto invariants: SHA-256 hex digest length 64
  (`src/cadrumo/domain/transactions/tests/test_split_lineage.py:42`), 32-byte
  keys (`src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py:253`).
- Persisted-format lineage: `schema_version == 1` pins
  (`src/cadrumo/tests/test_persisted_format_enrollment.py:176`) and the frozen
  `RELEASED_FORMAT_FLOORS` regime.
- Statutory and registry values: casilla ids and numbers, rates, thresholds,
  diseno record widths, manual-oracle `expected_by_casilla_id` figures.
- Operator-mandated policy knobs: `MIN_DISTINCT_RENTA_YEARS = 2`
  (`src/cadrumo/core/access_gate/_authorization.py:48-51`; "The owner mandate
  is two distinct years"), `MAX_ACTIVE_TOOLSETS = 3`
  (`src/cadrumo/entrypoints/mcp/_toolsets.py:106`).
- Fixture-derived counts: `len(operations) == 6` for a two-NIF checker plan
  (`src/cadrumo/domain/calculations/registry/tests/test_aeat_nif_iva_oracle.py:107`)
  and the pervasive insert-one-assert-one roundtrip counts - these restate the
  test's own inputs, not the tree.
- Render-measured coverage floors in the declaracion real-render campaign -
  measured from real renders and justified against them (dispatch brief; the
  campaign's ADR is linked from its feature index).

### Not investigated, and limits

An `rg` sweep cannot see a census hidden behind one indirection
(`EXPECTED = 41` used later as `== EXPECTED`); the constant-name sweep caught
conventionally-named integers only, so exhaustiveness over indirected pins is
not claimed. Docs prose and `.vault/` records were left to the concurrent
consistency sweep; trees outside `src/cadrumo/` and `dev/` baselines were out
of scope. Per-class site counts are derivable from the itemized lists above and
are not free-standing claims.

## Sources

- `src/cadrumo/tests/test_lazy_import_policy.py:1-60,833-872,1126-1190`
- `src/cadrumo/tests/test_import_hygiene_gate.py:1-120`
- `src/cadrumo/tests/_size_budget.py:75-129`
- `src/cadrumo/tests/test_codebase_size_budgets.py:193,205`
- `src/cadrumo/tests/test_modelo_authorization_gate.py:145-215`
- `src/cadrumo/tests/test_registry_locale_key_parity.py:84-97`
- `src/cadrumo/tests/test_hardcoded_constants_inventory.py:1-75,191`
- `src/cadrumo/core/access_gate/_authorization.py:45-78`
- `src/cadrumo/domain/portals/tests/test_registry.py:60-90,175-200`
- `src/cadrumo/domain/portals/tests/test_smoke.py:30`
- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py:236-265`
- `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification.py:230-253`
- `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_normatives.py:500-526`
- `src/cadrumo/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py:170-190`
- `src/cadrumo/domain/usage_ratios/tests/test_model.py:115-130`
- `src/cadrumo/domain/calculations/registry/tests/test_aeat_nif_iva_oracle.py:95-110`
- `dev/import_hygiene_baseline.json`, `dev/import_hygiene_test_debt.json`
- Audit stem `2026-07-25-test-harness-honesty-false-green-gates-audit`
- HEAD at measurement: commit `d1e91cb00f2d`
