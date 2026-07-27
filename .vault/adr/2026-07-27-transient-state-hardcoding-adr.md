---
tags:
  - '#adr'
  - '#transient-state-hardcoding'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-27-transient-state-hardcoding-research]]"
  - '[[2026-07-25-test-harness-honesty-false-green-gates-audit]]'
---
# `transient-state-hardcoding` adr: `no hardcoded transient state` | (**status:** `accepted`)

## Problem Statement

The operator mandates removal of hardcoded numbers that encode transient state:
a number describing how the tree happens to be right now has no point being
written down, because it is wrong the moment the state moves, nothing fails
when it goes stale, and it then misleads. The tree carries a measured
population of such numbers in executable gates - census pins in tests, ratchet
counters, slack-rotted budget pins - inventoried in
`2026-07-27-transient-state-hardcoding-research`, and its records showed the
same failure in prose (counts corrected only where someone happened to look; a
consistency sweep is correcting those separately). Two coding agents are queued
to implement; a ruling must fix the boundary, settle the hard middle (ratchets
and baselines), and name what must not be swept, before they land anything.

## Considerations

- A count is substitution-blind: cardinality cannot distinguish one member set
  from another of the same size, so a census pin admits an undetected swap
  (research, mechanism section).
- Unguarded pins rot silently: 8901 lines of aggregate slack in the
  size-budget overrides; the lazy-import gate's own recorded "84 sites of dead
  headroom" history (research, T4 and T3).
- Zero-slack pins do not rot but serialize concurrent writers on one integer
  line and mis-merge under concurrent increments (research, mechanism section).
- Prose beside a maintained pin still rots ("twelve" vs 15; research).
- The grounded surface is legally load-bearing: statutory values, casilla
  numbers, oracle figures, and format floors are governed by
  `registry-calculation-legal-grounding`,
  `verification-grounding-needs-oracle-evidence`, and the compatibility
  lifecycle; an over-broad sweep does real harm.
- Sound identity-keyed patterns already ship in this tree to converge on
  (research, convergence-targets section).
- Rule codification is retired (2026-07-13); this ADR is the governing record,
  enforced by the gates themselves, not by a new always-on rule.

## Considered options

- **Status quo: pinned counts as deliberate-change tripwires.** Pro: forces a
  human edit on set growth. Con: fires without naming the change,
  substitution-blind, integer merge hazard, and the unguarded variants
  demonstrably rot. Rejected.
- **Blanket ban on hardcoded numbers.** Pro: trivially applicable. Con: sweeps
  statutory rates, form arithmetic, format widths, and oracle figures whose
  hardcoding is correct and legally required. Rejected as harmful.
- **Identity over cardinality (chosen).** Every review-forcing declaration is
  an identity-keyed set with two-sided liveness; counts are derived at runtime,
  never checked in; grounded invariants are exempted by an explicit boundary
  test.
- **Central expected-counts manifest.** Pro: one place to update. Con: still
  cardinality; relocates the staleness instead of removing it. Rejected.

## Constraints

- Implementation lands exclusively through the queued coding agents; this
  record designs and inventories, it does not implement.
- Shared factory worktree: the gate files are contended surfaces; the T3
  migration edits a file with live peer-WIP risk and must follow the
  explicit-pathspec and abort-on-foreign-WIP discipline.
- The T2 normatives derivation must read revisions through the loaded registry
  authority, never directory listings, per
  `registry-revision-content-inline-or-fragmented`.
- The semantic code index is degraded; remediation verification must rest on
  `rg`, whole-file reads, and authority loads, not semantic search.

## Implementation

### The boundary test

A checked-in number is **transient state** iff the working tree can recompute
it from itself - its truth is "what the tree happens to contain at some HEAD".
It is **grounded** iff only an authority outside the tree can invalidate it
(BOE/AEAT text, an official form or diseno, a format or crypto specification, a
released-data floor, an explicit operator mandate) or it restates the test's
own fixture inputs. The two-question form a future author applies in seconds:

1. *Who must edit this number when the tree changes?* If the answer is
   "whoever notices", it is transient.
2. *What breaks if nobody does?* If the answer is "nothing" or "a gate that
   merely demands the number be retyped", it is transient.

Transient numbers are forbidden in production code, tests, and gates. We will
express every review-forcing declaration as an identity-keyed set - named
entries with two-sided liveness (every live site declared, every declared entry
live) and a reason per entry - and derive any count from the set at runtime.
A checked-in count is never the instrument.

### Ruling on the hard middle: ratchets and baselines

The review-forcing *function* of a ratchet is legitimate; the integer
*instrument* is not. A ratchet is an identity-keyed declaration as above; the
"increase requires a same-commit edit" property is preserved (adding a live
site without its declared entry fails) and improved (the failure names the
site; a member swap no longer passes).

A checked-in counter is tolerable only where identity enumeration is
demonstrably impractical. The research found no such site in this tree. Any
counter nevertheless retained must carry all three legitimacy conditions: a
zero-slack companion assertion pinning it to the live measurement, adjacency
to the identity data it summarizes, and a failure message stating the exact
re-derivation. A counter missing any of the three is a defect outright.

Two adjacent classes are ruled legitimate and are not ratchets-in-disguise:

- **Tolerance-banded policy ceilings** (the size budgets): legitimate as
  budgets, provided every override pin sits under the staleness detector's
  declared band. A "no headroom" comment beside a slack-carrying pin is a
  defect.
- **Anti-vacuity floors with deliberate declared slack** (minimum-scanned
  bounds): legitimate, because they measure instrument health against an
  order-of-magnitude bound, not the tree against itself.

### Remedies per class (sites enumerated in the research, T1-T4)

- **T1 - counts redundant beside an identity assertion: delete.** Remove the
  `len(...) == N` line (or the count-only test) and the stale ordinal prose
  beside it. Four sites: the ledger binding-kind taxonomy count, the
  usage-ratio category count (and its "twelve" docstring), the portal-registry
  count test (the enum-closure test stays), and the authorization-gate
  `FLEET_SIZE == 73` line (the two derivation asserts above it stay; the
  enum-to-registry parity gate already guards the denominator).
- **T2 - tripwire counts with no identity companion: replace with identity or
  derived closure.** Locale-key parity: assert the category stems present in
  the scanned keys equal the registry's category-id set, keep the `.quote`
  exclusion, drop `== 86`. Namespace registry: assert non-emptiness, keep the
  structural `all(...)` invariants, drop `== 67` from assert and test name.
  Corpus catalogue checks: build the expected id/file set from the same
  manifest or loaded registry revisions the loop reads (the normatives set
  derived from revisions crossed with their declared formal-withholding
  sources, loaded through the authority) and assert set equality with
  `checked`, moving the hand-derivation comments into code. Portals: derive
  the expectation from `len(Portal)` / `len(mapping)` everywhere including the
  asserted log text; the smoke test asserts enum closure instead of a count.
  Pattern-control parity: assert key-set equality between the control table
  and the module's declared patterns, drop `== 5`.
- **T3 - zero-slack ratchet counters: migrate to a function-keyed site
  inventory.** Replace the per-class site ceilings and the edge-count ceiling
  in the lazy-import gate with declared site entries keyed
  `(consumer_module, enclosing_qualname, target_module)`, grouped under the
  existing unsanctioned-class taxonomy, line numbers excluded from identity
  (the import-hygiene `_BaselineSite` precedent). The gate asserts two-sided
  set equality between live and declared sites; zero slack holds by
  construction; the ports-inversion class becomes an empty declared bucket, so
  its hard zero is structural. Per-class counts appear only in failure output,
  derived. Accepted costs: a several-hundred-entry declaration, and a function
  rename inside an allowlisted module reds the gate - intended, since a moved
  deferral is re-reviewed.
- **T4 - slack-rotted budget pins: re-derive and enroll.** Regenerate every
  per-module and per-callable override pin to measured actuals through the
  gate's own measurement path, enroll all overrides under the existing
  staleness detector and band, and delete or truthify "no headroom" comments.
- **Records and prose, going forward:** a count in a vault document, docstring,
  or comment is a dated observation. It carries an as-of anchor (date or
  commit) or the method that produced it, or it is phrased as a derivation the
  reader can re-run. An unanchored present-tense count is a defect. The
  concurrent consistency sweep owns retroactive corrections; this rule governs
  new authorship, including this feature's own documents.

### What must not be swept

Grounded numbers stay hardcoded; a later agent applying this ruling must not
touch: statutory and registry values (rates, thresholds, casilla ids and
numbers, deadline windows) in registry TOML and `core/external_constants.py`;
manual-oracle `expected_by_casilla_id` figures and diseno record
positions/widths; `schema_version` literals, durability floors, and
`RELEASED_FORMAT_FLOORS`; crypto and format lengths (64-hex SHA-256, 32-byte
keys); operator-mandated policy knobs (`MIN_DISTINCT_RENTA_YEARS`,
`MAX_ACTIVE_TOOLSETS`); fixture-derived counts restating a test's own inputs;
anti-vacuity floors with declared slack; and render-measured coverage floors
justified against real renders. A doubtful case is settled by the boundary
test applied to that number, not by resemblance to anything on either list.

## Rationale

The knockout is dominance: a census count admits an undetected member swap, so
it protects strictly less than the identity set while costing the same edit on
every legitimate change - and the identity set's failure names the change. A
checked-in count is therefore never the best available instrument; the only
question per site is which identity form replaces it, settled per class above.
The rot evidence (T4's measured slack, T3's recorded headroom history, the
"twelve"-vs-15 prose drift) is documented in
`2026-07-27-transient-state-hardcoding-research` and the harness-honesty audit
`2026-07-25-test-harness-honesty-false-green-gates-audit`.

One precision against the mandate as issued, stated because the dispatch asked
for honest disagreement: zero-slack ratchet counters (T3) are not the
silent-rot pathology - they fail loudly when stale. They are condemned on
dominance, writer-serialization, and merge-hazard grounds instead, which makes
their remediation real but lower urgency than T1, T2, and T4. The blanket-ban
option was rejected for the same honesty in the other direction: the grounded
surface is load-bearing and legally governed, and sweeping it would be the
more damaging error.

## Consequences

- Gates stop being able to go stale by construction; failures name the changed
  member; substitution becomes detectable; concurrent agents stop contending
  on single integer lines.
- One-time migration cost, largest in T3 (a several-hundred-entry declaration)
  plus ongoing qualname-rename churn in the lazy-import gate - accepted as the
  price of reviewable identity.
- Residual risk: identity sets can be rubber-stamped exactly as counts were.
  Mitigation is the existing reasoned-entry discipline (a reason and
  disposition per entry, as the import-hygiene baselines already carry) and
  two-sided liveness, which forces a stamp to name what it admits.
- Record-prose counts become re-derivable dated observations; the consistency
  sweep and this ruling are complementary, and neither subsumes the other.
