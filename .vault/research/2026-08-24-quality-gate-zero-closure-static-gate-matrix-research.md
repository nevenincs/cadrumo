---
tags:
  - '#research'
  - '#quality-gate-zero-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:66c047cc0ab76b87ea0781d05d19f491124ccc8a2164815b04e6b4149af391c6'
related:
  - '[[2026-08-24-quality-gate-zero-closure-failure-cluster-topology-reference]]'
  - '[[2026-06-09-quality-hardening-campaign-research]]'
  - '[[2026-06-04-repo-health-triage-research]]'
  - '[[2026-07-10-gate-drift-reconciliation-research]]'
  - '[[2026-08-14-test-harness-sanity-two-lane-campaign-research]]'
---
# `quality-gate-zero-closure` research: `Quality gate zero closure static-gate matrix`

The zero-closure problem is an evidence and ownership problem, not a reason to
lower the gates. At the 2026-08-24 discovery snapshot (HEAD
`298b07676e55464fad9e5ab39460a168baeb9408`, with a shared dirty worktree), the
static tree reported 5,182 type diagnostics (1,949 ty, 1,206 pyrefly, and 2,027
basedpyright), 86 Ruff findings, 310 files needing format, nine dependency
findings after the recipe's test exclusions, 23 failed ratchet tests with 143
passing, and 18 Vault hard errors (12 frontmatter and six schema). Those values
are a re-fetchable WIP snapshot, not a debt baseline. The evidence favors
root-cause batches owned by the plans already touching each path, followed by
clean-snapshot verification; the ADR must settle campaign authority, ordering,
and the exact closure predicate.

## Findings

### The gate contract already defines exact, independent hard checks

The local static surface is explicit: `justfile:225-253` exposes style, format,
types, import, relative-import, and dependency checks, while
`dev/quality/suite.py:37-44,94` runs the same gates to completion and aggregates
failures. CI invokes the static commands separately at
`.github/workflows/ci.yml:153-163`. Type scope is deliberately strict:
`dev/quality/types.py:29-31,73,109-183,263-280` runs ty across `src` and
pyrefly/BasedPyright over their configured strict subset, and
`pyproject.toml:853-930` sets all ty rules to errors, permits no unresolved
imports, excludes only the declared pyrefly test tree, and makes unnecessary
type-ignore comments errors.

A threshold, diagnostic baseline, new-error-only rule, or additional exclusion
would produce a green signal without proving zero. The project quality rule
requires real behavior and rejects suppressions, skips, xfails, and tautological
assertions at `.codex/rules/aeat-quality-gates.md:10-11,56-60,78-85`. The ADR
therefore needs to decide how the existing hard contract is scheduled and
reported, not whether its truth condition should be weakened.

### Type output is a small set of repeated root-cause families, not thousands of unrelated repairs

The current type run has concentrated clusters: ty is led by
`call-non-callable` and `unresolved-attribute`; pyrefly is led by
`bad-argument-type`, with `src/cadrumo/application/calculations/_row_set_assembly.py`
carrying the largest file cluster; BasedPyright is led by unknown-member and
unknown-argument families, with the auth operators and registry connectivity
surfaces among the largest files. The wrapper's normalised checker/rule/file
report at `dev/quality/types.py:235-280` is the right measurement surface; raw
multi-thousand-line output is available only through the explicit audit mode.

The earlier quality-hardening campaign demonstrates the leverage of typed
boundary repairs: its recorded sequence reduced the type surface from 2,383 to
1,126, then through mechanical classes to 850 and a genuine-drift slice to 360,
without blanket ignores
(`.vault/audit/2026-06-09-quality-hardening-campaign-audit.md:107-127,167-188,532-543,568-578`).
Its later floor was 12 diagnostics, all in dirty peer-owned files, and its
module-size work was explicitly deferred to the owning feature rather than
edited through a shared hot file
(`.vault/audit/2026-06-09-quality-hardening-campaign-audit.md:649-689`).

The alternatives are (a) checker/rule-class reductions first, (b) package-owner
slices around the largest files, or (c) a baseline or ignore list. The first two
preserve causal evidence and can be measured after every batch; the third is
incompatible with the configured hard contract and would hide debt. The ADR
must settle whether root-cause class order is globally coordinated or delegated
to the active feature owners, and what clean-snapshot evidence closes a cluster.

### Ruff and formatting are mostly mechanical, but the current syntax failures make blanket fixing unsafe

The current Ruff run reports 86 findings, dominated by import ordering and line
length. The largest cluster is the export producer
(`src/cadrumo/application/filing/_export_producer.py:589-832`); the same
snapshot includes four syntax diagnostics in
`src/cadrumo/entrypoints/cli/tests/test_action_reconciliation_invocation_scope.py:52-75`
and smaller `__all__`, unused-import, and test-file import clusters. The
format check reports 310 files needing reformatting. The configured line length
is 120 at `pyproject.toml:477-488`, so a formatter run is a deterministic
mechanical operation, but it still rewrites peer-owned files.

Three choices remain: run a repository-wide formatter and auto-fix, apply
owner-scoped batches, or add exclusions/noqa comments for active work. The
syntax blockers and the shared-tree ownership map make owner-scoped batches the
safer evidence shape; exclusions would conceal debt and broad rewrites can
collide with active plan edits. The ADR must settle who owns mechanical cleanup
in paths already covered by TUI, profile, registry, and storage plans, and how
each batch is revalidated against the full static surface.

### Dependency drift mixes a gate configuration error with missing direct declarations

The recipe intentionally scans production and registry code while excluding
test paths at `justfile:250-253`. On the discovery snapshot it found nine
records: seven `dev` imports classified as a declared dev dependency, one
transitive `grimp` import, and one transitive `tomlkit` import. The dev group
currently starts at `pyproject.toml:340-355` and does not declare `grimp` or
`tomlkit`.

The `dev` findings are likely a first-party classification question: the
recipe marks `cadrumo` as known-first-party but not `dev`; declaring a
project-local `dev` package would be misleading. `grimp` and `tomlkit` are
direct imports and need either direct dev declarations or a code path that no
longer imports them. The alternatives are to classify `dev` correctly, add the
missing direct packages, or add per-rule ignores. Only the first two preserve
deptry's signal. The ADR must settle the canonical dependency declaration
surface and whether the scan command is allowed to evolve its first-party map
as the repository layout changes.

### Ratchet failures are policy debt with a named owner, not permission to install allowlists

`justfile:462-464` runs the ratchet suite without the cache provider across
inventory, markers, relative imports, skip/xfail, doubles, monkeypatch, broad
raises, bare except, and tautology checks. The current run is 23 failed and 143
passed. The highest-signal failures include stale post-relocation assertions in
`dev/tests/test_test_inventory.py:929-959,1511-1547,1644-1653`: those tests
still treat their own old source-tree path as a package test even though
`dev/tests/_project_inventory.py:18-53` declares project tests under `dev` and
`docs`. Other reds are marker policy
(`dev/tests/test_marker_integrity.py:1043-1174`), 26 absolute intra-package
imports (`src/cadrumo/tests/test_relative_imports_only.py:82-91`), forbidden
shortcuts (`dev/tests/test_no_skip_xfail.py:553,872`), broad raises
(`dev/tests/test_no_broad_exception_raises.py:331-345`), mock/double inventory
(`dev/tests/test_mock_inventory.py:574-592`), and monkeypatch inventory
(`dev/tests/test_monkeypatch_inventory.py:313-318`).

The active test-harness plan explicitly owns marker/live-import enforcement,
monkeypatch removal, central-harness ownership, and the reopened W09 census
(`.vault/plan/2026-08-14-test-harness-sanity-plan.md:115-153,185-225`). The
import-centralization, CI-lane, profile-custody, registry, source-casilla, and
secure-storage plans own overlapping test and gate paths. A direct coordinator
sweep could clear one ratchet while invalidating another plan's topology or
fixtures. A no-monkeypatch allowlist is expressly rejected by the companion
audit, which records that the gate must remain allowlist-free
(`.vault/audit/2026-08-15-test-harness-sanity-monkeypatch-criterion-deferral-audit.md:22-23,92-103`).
The ADR must settle handoff rules and whether zero ratchets is the campaign's
final predicate or a joined predicate whose rows remain with their active
owners until their plans close.

### Vault hard errors are document repairs with separate ownership from code gates

A global `vault check all` at this snapshot reports 12 frontmatter errors on
three hand-authored records
(`.vault/audit/2026-08-23-issue-113-operator-gate-audit.md`,
`.vault/reference/2026-08-23-registry-unblock-loop-reference.md`, and
`.vault/reference/2026-08-24-registry-unblock-loop-reference.md`) and six
schema errors on four ADRs and two plans lacking grounding references. Warnings
also include template annotations, orphans, feature-index drift, and body
hygiene; warnings and hard errors must be tracked separately.

The Vault rules require every mutation to use the owning CLI and permit prose
editing only after a CLI scaffold
(`.codex/rules/vaultspec-cli.builtin.md:13-19,67-70`). The body hash and
modified stamp are machine-attested by mutating verbs
(`.codex/rules/vaultspec.builtin.md:193-201`). A broad global repair could
rewrite peer documents and alter their provenance graph; scoped owner repairs
can add the missing metadata or references while preserving the audit trail.
The ADR must settle whether this campaign owns coordination only, or may repair
unowned records, and whether closure means hard-error zero with warnings
explicitly inventoried or warning zero as well.

### Shared-worktree evidence changes the correct campaign shape

The earlier gate-drift audit explains why numbers from this workspace are not a
release candidate: it recorded thousands of dirty files and separated current
WIP from committed HEAD
(`.vault/audit/2026-07-08-gate-drift-reconciliation-audit.md:18-20`). This
discovery reproduced the same phenomenon: type, Ruff, dependency, and Vault
counts changed while concurrent edits landed. The active plans are not empty
placeholders: secure-storage owns a repository-wide gate sweep in
`.vault/plan/2026-08-22-secure-storage-performance-hardening-plan.md:146-160`;
registry completeness still owns live proof wiring in
`.vault/plan/2026-08-24-registry-completeness-closure-plan.md:48-79`; and
source-casilla still owns the connected-proof and row-observation surface in
`.vault/plan/2026-08-22-source-casilla-integration-plan.md:122-126,293-400`.

A single-agent whole-tree rewrite is fast to start but cannot distinguish peer
WIP from regressions and risks modify/modify collisions. Owner-bound batches
with a clean verification snapshot preserve both provenance and gate meaning.
The ADR must define the snapshot protocol (HEAD capture, dirty-path ledger,
owner handoff, re-read HEAD before close) and the boundary between a
coordination plan and existing feature plans.

### Bounded investigation

This research covered static gates, the dependency recipe, the ratchet suite,
Vault hard errors, active plan ownership, and comparable health campaigns. It
did not run the full unit/integration suites, semgrep/security scans, package
builds, or external advisory checks. The resident semantic RAG service rejected
the available client/daemon version pair during discovery, so targeted
`rg` plus the Vault CLI were used for confirmation; the semantic index should be
revalidated before an ADR claims exhaustive architecture discovery.

## Sources

- `justfile:225-253,462-464`
- `dev/quality/suite.py:37-44,94`
- `dev/quality/types.py:29-31,73,109-183,235-280`
- `pyproject.toml:340-355,477-488,853-930`
- `.github/workflows/ci.yml:153-163,235-242`
- `.codex/rules/aeat-quality-gates.md:10-11,56-60,78-85`
- `.codex/rules/vaultspec-cli.builtin.md:13-19,67-70`
- `.codex/rules/vaultspec.builtin.md:193-201`
- `.vault/audit/2026-06-09-quality-hardening-campaign-audit.md:107-127,167-188,532-543,568-578,649-689`
- `.vault/audit/2026-07-08-gate-drift-reconciliation-audit.md:18-20`
- `.vault/audit/2026-08-15-test-harness-sanity-monkeypatch-criterion-deferral-audit.md:22-23,92-103`
- `.vault/plan/2026-08-14-test-harness-sanity-plan.md:115-153,185-225`
- `.vault/plan/2026-08-22-secure-storage-performance-hardening-plan.md:146-160`
- `.vault/plan/2026-08-22-source-casilla-integration-plan.md:122-126,293-400`
- `.vault/plan/2026-08-24-registry-completeness-closure-plan.md:48-79`
- `uv run --no-sync python -m dev.quality.types` (2026-08-24 dirty-tree snapshot)
- `uv run --no-sync ruff check . --output-format concise` (2026-08-24 dirty-tree snapshot)
- `uv run --no-sync ruff format --check .` (2026-08-24 dirty-tree snapshot)
- `uv run --no-sync deptry src/cadrumo dev/registry --known-first-party cadrumo --extend-exclude ".*test_.*[.]py" --extend-exclude ".*_test_.*[.]py" --extend-exclude ".*[\\/]tests[\\/].*"` (2026-08-24 dirty-tree snapshot)
- `uv run --no-sync pytest -q -p no:cacheprovider -rsf dev/tests/test_test_inventory.py dev/tests/test_marker_integrity.py src/cadrumo/tests/test_relative_imports_only.py dev/tests/test_no_skip_xfail.py dev/tests/test_mock_inventory.py dev/tests/test_monkeypatch_inventory.py dev/tests/test_no_broad_exception_raises.py dev/tests/test_no_bare_except.py dev/tests/test_no_tautology.py --tb=short` (2026-08-24 dirty-tree snapshot)
- `uv run --no-sync vaultspec-core vault check all --json` (2026-08-24 dirty-tree snapshot)
