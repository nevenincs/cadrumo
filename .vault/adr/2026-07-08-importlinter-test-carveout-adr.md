---
tags:
  - '#adr'
  - '#importlinter-test-carveout'
date: '2026-07-08'
modified: '2026-09-11'
body_hash: 'sha256:b88f1b47fdc7f41e3d777120f4b81c9c0723598c083ca6e51979eeac2df33089'
related:
  - '[[2026-07-10-importlinter-test-carveout-research]]'
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-09-11-import-centralization-import-authority-drift-audit]]'
---

# `importlinter-test-carveout` adr: `Test-file import-linter carve-out` | (**status:** `accepted`)

## Problem Statement

Three `.importlinter` contracts (`Domain must not import adapters`,
`Core must not import outer layers`, `AEAT layered architecture`) carried
per-file `ignore_imports` entries for every roundtrip/anti-tautology/fixture
test that legitimately crosses a layer boundary to construct a real adapter
(`aeat-roundtrip-discipline`). Two new roundtrip test files
(`domain.invoices.tests.test_secure_storage_roundtrip`,
`domain.modelos.tests.test_repository_sensitivity_class`) landed without a
matching exemption line, breaking all three contracts. The per-file-entry
model does not scale: every new roundtrip test is a required `.importlinter`
edit, and the file had grown past a thousand lines of near-duplicate entries.

## Considerations

- `unmatched_ignore_imports_alerting = error` on every contract means an
  `ignore_imports` line that matches zero real edges is a hard failure, so a
  wildcard carve-out must be verified against the live import graph, not
  authored speculatively.
- Production cross-layer coupling must remain individually pinned and
  loudly caught (the `application -> adapters` ADR sec. 538 allowance, the
  per-repository ports-inversion edges, the `core/resources/_repos` deferred
  loaders) — a carve-out that also swallows production edges defeats the
  contracts' purpose.
- `import-linter` 2.12 / `grimp`'s `ignore_imports` expressions support `*`
  (one module segment) and `**` (one-or-more segments, no zero-segment
  match); confirmed empirically that covering "a test module at any nesting
  depth under a layer" needs two lines per (source, target) pair: the
  zero-intervening-segment case (`cadrumo.domain.tests.**`) and the
  one-or-more-intervening case (`cadrumo.domain.**.tests.**`).
- A handful of test edges route through the shared `cadrumo.tests.*` /
  `cadrumo.locales` cross-cutting helper packages (not declared layers
  themselves) that transitively reach a forbidden outer layer; the direct
  edge into the helper must be exempted, not the transitive target.
- `conftest.py` files sitting directly in a layer subpackage (not nested
  under a `tests/` folder) are the same fixture pattern and need their own
  `**.conftest` coverage.

## Considered options

- **Per-file entries for the 2 new tests only.** Rejected: restores green
  contracts today but repeats the exact scaling failure that caused this
  break; the next roundtrip test breaks the gate again.
- **Wildcard carve-out for every `.tests.`/`conftest` importer, verified
  against the live graph.** Chosen: a small, fixed set of `ignore_imports`
  wildcards (verified to match at least one real edge each) exempts every
  test/fixture module at any depth under a layer, while every individually
  pinned production edge is preserved verbatim.
- **Loosen the contracts to allow test imports structurally (e.g. exclude
  `tests` packages from the analyzed graph).** Rejected: this would also
  hide a genuine production leak introduced inside a test-adjacent module
  and removes the contracts' ability to warn on new production coupling.

## Constraints

- Every wildcard line added must be confirmed via
  `grimp.build_graph("aeat").find_matching_direct_imports(...)` to match at
  least one real edge in the current tree before being committed; an
  unmatched wildcard is an immediate hard failure under
  `unmatched_ignore_imports_alerting = error`.
- The carve-out is scoped to the 3 contracts that were actually broken;
  `Domain must not import application` (already passing) is left untouched.

## Implementation

Each of the 3 contracts' `ignore_imports` list is split mechanically into
"test-importer" entries (importer path contains a `tests` segment, or its
last segment is `conftest`) and "production" entries (everything else). Every
test-importer entry is dropped and replaced by a small fixed set of `*`/`**`
wildcard lines — one pair per (source-layer, target-layer) combination that
has at least one real matching edge today: `<layer>.tests.**` for a test
module directly under the layer root, `<layer>.**.tests.**` for a test module
nested under an arbitrary number of subpackages, plus `<layer>.**.conftest`
for a `conftest.py` outside a `tests/` folder, and two narrow lines routing
through the shared `cadrumo.tests.cli_runner` / `cadrumo.locales` helper packages
that transitively reach an outer layer. Every production entry (the
`application -> adapters` ADR sec. 538 allowance, the per-repository
ports-inversion edges, the `core/resources/_repos` deferred loaders) is kept
verbatim, individually pinned. The 4 prorrata-owned production edges
(`application.modelo._revision_persistence`,
`application.calculations._prorrata_regularizacion`,
`application.aggregation._iva_ledger` into
`adapters.persistence.profile.prorrata_register` /
`adapters.persistence.storage`) are deliberately left unexempted for the
prorrata campaign to resolve on its own schedule.

## Rationale

The wildcard set is derived from, and verified against, the live import
graph rather than authored speculatively: every line was confirmed via a
direct `grimp` query to match at least one real edge before being added, so
the carve-out cannot silently swallow a combination that never occurs today,
and `unmatched_ignore_imports_alerting = error` continues to catch a stale
wildcard the same way it caught stale per-file entries. Splitting strictly on
"does the importer path contain a `tests` segment or end in `conftest`"
keeps the production allowance untouched byte-for-byte, so a new production
`application -> adapters` edge outside the ADR sec. 538 list, or any new
`domain -> adapters` production edge, still fails the gate loudly.

## Consequences

A new roundtrip, anti-tautology, or fixture test anywhere under
`domain`/`application`/`core` that imports an outer-layer adapter, or a new
`conftest.py` doing the same, needs no `.importlinter` edit going forward —
the two-line-per-direction wildcard already covers it. The trade-off is that
the wildcard is coarser than a per-file pin: it cannot distinguish "this
specific test legitimately reaches this specific adapter" from "any test in
this layer reaches any adapter," so a test that reaches an adapter by mistake
(rather than by roundtrip-discipline design) will not be caught by this gate;
that class of review shifts to code review of the test itself. The 4
prorrata production violations remain visibly `BROKEN` under `AEAT layered
architecture` until the prorrata campaign either adds its own justified
exemption or removes the coupling — this is the intended, honest state.

## 2026-09-11 amendment: the test carve-out is retired

The wildcard carve-out decided above is withdrawn in full. It conflicts with the accepted closed import model and has hidden exactly the class of architectural drift the gate must reject. This amendment is the controlling disposition of this record.

Every test, fixture, helper, and `conftest.py` under `src/` inherits the dependency permissions of its nearest owning package. A core test has core permissions; a domain test has domain and core permissions; an application test has application, domain, core, and inward-owned-port permissions. Test code does not import a concrete outer adapter merely to arrange a fixture. A cross-layer round trip or integration test moves to the outermost adapter or entrypoint seam it exercises.

No module under `src/`, including any test-only or artifact-excluded module, may import or dynamically load `dev`, root test support, or another repository-only surface. Moving an import into a helper, a local scope, `TYPE_CHECKING`, a string target, or a shared test package does not change the dependency.

All wildcard test ignores and test-specific forbidden-direction bypasses are migration debt to remove, not a sanctioned baseline. Structurally legal directions replace them in `.importlinter`; no replacement test allowlist is created. The authoritative planted-defect suite proves through `just check-imports` that an owner-lane test crossing outward and any `src` test importing `dev` both fail.
