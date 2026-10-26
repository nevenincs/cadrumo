---
tags:
  - '#research'
  - '#transient-state-hardcoding'
date: '2026-07-27'
modified: '2026-10-03'
body_hash: 'sha256:d9f2fd3b4e3a66cccd827c216b29871a53682deea5b8566d5ba07e1aef87efea'
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
- Whole-context reads of the former source file,

  the former source file, and each census-assert site below.

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
companion was added .

Zero-slack pins do not drift but are substitution-blind and serialize writers.
`test_ceilings_carry_no_slack_over_the_live_counts`
 pins every ceiling AT its
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

  `assert FLEET_SIZE == 73` after lines 155-156 tie `FLEET_SIZE` to the fleet
  tuple. Production already derives it: `FLEET_SIZE = len(CANONICAL_MODELO_FLEET)`
  , and an accidental
  `Modelo` enum edit is separately caught by the enum-to-registry parity gate
  . The docstring narrates count
  history ("became 73 when Modelo 145 was added").

### T2 - census counts pinned as deliberate-change tripwires, no identity companion

These pins exist to force a human re-look when a registry or corpus set changes
(one documents that intent explicitly). They fire on any cardinality change but
cannot name the change and cannot see a substitution.

  `len(keys) == 86`; the docstring (lines 91-93) states the pin is deliberate.
  The carve-out invariant actually protected is line 97 (no `.quote` keys),
  asserted independently.
- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py:252`
  - `len(definitions) == 67`; the test name (`test_all_67_namespace_rows...`,
  line 249) encodes the census too. The structural `all(...)` assertions that
  follow are the real invariant.

  - `len(checked) == 18` closing a loop over the bundled Modelo-100 corpus
  manifest (anti-vacuity is the residual value; the count also pins the
  title-filter skip behaviour of lines 234-239).

  - `len(checked) == 51`, with a hand-derivation comment (lines 514-522)
  reproducing the arithmetic (28 + 10 + 13) and the retired prior value (72).
- `src/cadrumo/domain/portals/tests/test_registry.py:182` and `:196` -
  `len(mapping) == 41`; lines 186-187 additionally assert the literal log text
  "loaded 41 portal entries" (the production message interpolates the count;
  the test hardcodes it).
- `src/cadrumo/domain/portals/tests/test_smoke.py:30` -
  `len(PORTAL_REGISTRY) == 41`.

  `len(_PATTERN_CONTROLS) == 5` ("every scan pattern in this module needs a
  control pair") - an intra-module parity claim expressible as key-set equality
  against the patterns the module declares.

### T3 - checked-in ratchet counters under a zero-slack pin

the former source file declares
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

### T4 - pins with unguarded slack

the former source file per-module and per-callable override pins
(drift measured above). The machinery for the sound form already exists in the
same module: tolerance bands (`default_limit`, `headroom_ratio`, `slack_ratio`,
`slack_floor`, lines 117-129) and a stale-budget detector exercised by

### Sound patterns already in-tree (convergence targets)

- Identity-keyed baseline with two-sided equality:
  the former source file and the former source file -
  named, reasoned entries; the gate asserts both count-not-exceeded and
  named-set equality, with counts derived from the lists
  . Same shape:
  the former source file (locale honesty ratchet,
  reasoned entries).
- Derived production constant: `FLEET_SIZE = len(CANONICAL_MODELO_FLEET)`
  , commented "derived
  from the canonical fleet rather than hard-coded so the two cannot disagree".
- Registry-derived closure: `src/cadrumo/domain/usage_ratios/tests/test_model.py:121-127`
  re-derives the eligible category set from the registry and asserts equality -
  stale-proof by construction (the trailing count pin is the defect, not the
  closure).
- Anti-vacuity floors with declared, deliberate slack:
  `MIN_SCANNED_MODULES = 2000` and `MIN_SCANNED_CALLABLES = 7500`
   against a measured population of
  9933 production callables - order-of-magnitude scanner-health bounds, not
  tree pins.

### Numbers established as NOT transient (grounded)

- Format and crypto invariants: SHA-256 hex digest length 64
  (`src/cadrumo/domain/transactions/tests/test_split_lineage.py:42`), 32-byte
  keys (`src/cadrumo/adapters/persistence/storage/sql/tests/test_secure_objects_part1.py:253`).
- Persisted-format lineage: `schema_version == 1` pins
   and the frozen
  `RELEASED_FORMAT_FLOORS` regime.
- Statutory and registry values: casilla ids and numbers, rates, thresholds,
  diseno record widths, manual-oracle `expected_by_casilla_id` figures.
- Operator-mandated policy knobs: `MIN_DISTINCT_RENTA_YEARS = 2`
  (the former source file; "The owner mandate
  is two distinct years"), `MAX_ACTIVE_TOOLSETS = 3`

- Fixture-derived counts: `len(operations) == 6` for a two-NIF checker plan

  and the pervasive insert-one-assert-one roundtrip counts - these restate the
  test's own inputs, not the tree.
- Render-measured coverage floors in the declaracion real-render campaign -
  measured from real renders and justified against them (dispatch brief; the
  campaign's ADR is linked from its feature index).

### Worked example, live: an estate measurement is a function of its probe rules

Three probes of one question - "which extraction-profile targets' `value_kind`
disagrees with their casilla's `data_type`?" - returned three incompatible
answers, each presented or presentable as "the" measurement:

- The coordinator's sweep: "281 targets carry a `value_kind` and exactly seven
  disagree", used to justify a landed change as closing "the last incoherence
  in the estate". The seven exist only under an unstated discrimination
  (`year` distinguished from `integer`). Reported by the coordinator
  2026-07-27, self-corrected the same day.
- An independent sweep under the naive rule (`value_kind != data_type`,
  nothing else): four rows, none of them among the seven - `enum`-over-`text`
  and `enum`-over-`integer` pairings the first probe never adjudicated (the
  schema enforces no enum/text distinction). Reported with the correction.
- This research's reproduction (raw `tomllib` walk over every
  `extraction_profiles/*.toml` and sibling `casillas/*.toml` fragment under
  `src/cadrumo/_data/registry/aeat/modelos/`, all revisions, no authority
  load): 478 target rows carrying `value_kind` (77 with no casilla pairing
  resolved by the raw walk), 371 literal mismatches - because `value_kind`
  says `amount` where `data_type` says `money`, so even the "naive" rule
  embeds an unstated equivalence - and 114 residual rows (39 distinct
  casilla-kind-dtype triples) under the single stated equivalence
  amount~money, spanning at least eight distinct discrimination axes:
  text/year, text/period_code, amount/integer, amount/decimal, amount/year,
  amount/text, enum/text or enum/integer, and text over refinement types
  (nif, name, province_code, postal_code, municipality_code). Measured twice with identical results at HEADs `4ce8da72d6` and
  `5eac4410e7` (no registry working-tree modifications present), 2026-07-27.

The three numbers (7, 4, 114) do not disagree about the registry; they
disagree about three rules nobody stated: the POPULATION rule (which
revisions and targets are enumerated - 281 vs 478), the EQUIVALENCE rule
(amount~money assumed by everyone silently; amount~decimal, text~nif
undecided), and the DISCRIMINATION rule (year vs integer; enum vs text).
A derived count with any of the three unstated is irreproducible, and a
completeness claim built on it ("the last incoherence") is wrong the moment
a second party derives with different rules. The raw-walk numbers above are
themselves a third rule-set, not a refutation of the other two - which is
the finding.

### Not investigated, and limits

An `rg` sweep cannot see a census hidden behind one indirection
(`EXPECTED = 41` used later as `== EXPECTED`); the constant-name sweep caught
conventionally-named integers only, so exhaustiveness over indirected pins is
not claimed. Docs prose and `.vault/` records were left to the concurrent
consistency sweep; trees outside `src/cadrumo/` and `dev/` baselines were out
of scope. Per-class site counts are derivable from the itemized lists above and
are not free-standing claims.

## Sources

- `src/cadrumo/domain/portals/tests/test_registry.py:60-90,175-200`
- `src/cadrumo/domain/portals/tests/test_smoke.py:30`
- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py:236-265`

- `src/cadrumo/domain/usage_ratios/tests/test_model.py:115-130`

- Audit stem `2026-07-25-test-harness-honesty-false-green-gates-audit`
- HEAD at measurement: commit `d1e91cb00f2d` (gate inventory); commits `4ce8da72d6`, `5eac4410e7` (coherence-probe reproduction, identical results)
