---
tags:
  - '#research'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:d1fcd1f7bcf75aea3f7eebe12468f49233118d6281b534badc8b626840e95279'
related:
  - "[[2026-08-14-test-harness-sanity-audit]]"
  - "[[2026-06-05-test-topology-refactor-adr]]"
  - "[[2026-07-08-test-worker-count-policy-adr]]"
---

# `test-harness-sanity` research: `codebase-wide fixture canonicalization and harness remediation`

The campaign must canonicalize fixtures across the complete Python test
surface while repairing every finding in the test-harness audit without
weakening real-behavior coverage. Current-tree inventory finds 735 pytest
fixtures in 592 files, multiple exact-substitute clusters, eight non-fixture
harness gaps, and a direct conflict between the implemented xdist default and
the accepted worker-count decision. Existing topology and test-honesty ADRs
authorize ownership consolidation, but a successor decision is required for
worker authority and the verdict boundary of expensive real-process proofs.

## Findings

### Fixture duplication is codebase-wide and requires a census-driven migration

An AST inventory over `src`, `dev`, `packaging`, and root configuration,
excluding registry payload data, found 735 pytest fixture definitions in 592
files: 559 function-scoped, 161 module-scoped, 15 session-scoped, and 246
autouse. Exact-body clusters include 27 secure-runtime-profile fixtures, 17
secure-object-repository fixtures, 17 isolated profile/CLI storage fixtures,
five redeclarations of the canonical modelo `repos` fixture, five M200 dev
registry snapshots, and several registry revision snapshot families. The two
LLM conftests remain exact substitutes at
`src/cadrumo/llm/conftest.py:10-28` and
`src/cadrumo/adapters/outbound/llm/conftest.py:10-28`.

Body equality alone is insufficient: schema-loader fixtures share seven
bodies but differ in function/module scope, and CLI storage fixtures form at
least three constraint shapes. The migration therefore needs a recorded
census of decorator name, scope, autouse behavior, constraints, consumers,
and canonical owner before deletion. Blind promotion to a broad conftest risks
changing lifecycle and visibility even when bodies match.

### Existing topology authority already decides canonical ownership

The accepted topology decision requires tests and helpers to live at the
narrowest owning package and reserves `src/cadrumo/tests` for genuinely
cross-cutting surfaces (`.vault/adr/2026-06-05-test-topology-refactor-adr.md:68-86`).
The current central package still contains owner-specific behavior tests:
`src/cadrumo/tests/test_cli.py:1-19` tests only the core i18n default, while
`src/cadrumo/tests/test_output_language.py:1-76` exercises the application
profile/workflow stack. Fixture canonicalization and responsibility
deconflation implement the existing decision; they do not need a competing
ADR.

### Marker enforcement has two owners but incomplete live-test reach

The root hook calls only `_marker_hook.apply` (`conftest.py:98-109`), while
the banned-live-import scan and a second marker traversal live in the child
hook (`src/cadrumo/tests/conftest.py:128-164`). Eighteen `aeat_live` modules
currently live outside that child subtree and therefore receive marker
validation but not the advertised banned-import enforcement. A single root
collection owner can cover every live module and eliminate the duplicate
central traversal while retaining the same fail-closed policy.

### The real-behavior policy is currently red on committed monkeypatch use

The focused inventory gate at
`src/cadrumo/tests/test_monkeypatch_inventory.py:312-318` reports production
symbol mutation in OFX parsing, previous-filing handling, registry relation
closure, and previous-filing year coverage. The accepted pytest-only decision
forbids these controls (`.vault/adr/2026-04-17-pytest-only-testing-adr.md:21-34`).
Each domain needs a real input or explicit production seam; suppressing the
inventory, allowlisting sites, or renaming the fixture would preserve the
defect.

### Routine unit execution contains two avoidable recursive-process costs

Four tests in `src/cadrumo/tests/test_worker_count_hook.py:114-153` each boot
a fresh xdist pool, including six- and eight-worker probes, from an ordinary
unit module. Separately,
`src/cadrumo/tests/test_every_test_module_is_collectable.py:102-155` launches
a serial full-corpus child collection from the default unit lane. Both are
valuable end-to-end proofs, but their current placement makes every normal
unit campaign pay nested process and collection costs. Pure worker-resolution
logic and bounded malformed-module controls can remain routine unit evidence;
the installed-hook and full-corpus proofs need one explicit, independently
verdictable harness/collection lane.

### Worker authority is an unresolved ADR/code conflict

The accepted worker decision chooses operator-set native
`PYTEST_XDIST_AUTO_NUM_WORKERS` and rejects a repository default
(`.vault/adr/2026-07-08-test-worker-count-policy-adr.md:30-67`). Current code
does the opposite: `DEFAULT_WORKER_CAP = 6` and
`CADRUMO_PYTEST_WORKERS` always win on `-n auto`, preventing xdist's native
variable from participating (`src/cadrumo/tests/_worker_count_hook.py:20-70`).
No successor or supersession was found. Removing the hook restores the
accepted policy; retaining the repository default may fit later shared-host
experience, but requires fresh solo, CI, and concurrent measurements plus an
explicit successor decision.

### No active plan legitimately owns both lanes

The topology and test-honesty plans are complete. The CI lane-deconflation
plan remains 45/49, but its open work is an explicitly deferred external
runner boundary and its accepted decision requires independently verdictable
deterministic and load-sensitive passes. Absorbing fixture/harness remediation
there would conflate campaigns. A new roll-up plan can run two parallel waves:
fixture census/canonicalization and audit remediation, with the worker/lane
decision as their shared prerequisite.

### Shared-worktree overlap constrains sequencing, not scope

Current peer work modifies `src/cadrumo/tests/secure_sql.py` and adds
`src/cadrumo/tests/profile_capsule.py`, directly overlapping secure-runtime
fixture consolidation. That cluster should execute after coordination or peer
settlement. Independent marker-hook, worker-policy, monkeypatch, central-test,
registry-snapshot, and dev-fixture phases can proceed without narrowing the
codebase-wide fixture mandate.

## Sources

- `.vault/audit/2026-08-14-test-harness-sanity-audit.md:16-82`
- `.vault/adr/2026-04-17-pytest-only-testing-adr.md:21-60`
- `.vault/adr/2026-06-05-test-topology-refactor-adr.md:68-110`
- `.vault/adr/2026-07-08-test-worker-count-policy-adr.md:30-107`
- `.vault/adr/2026-08-05-ci-lane-deconflation-adr.md`
- `conftest.py:98-114`
- `src/cadrumo/tests/conftest.py:128-164`
- `src/cadrumo/tests/_worker_count_hook.py:20-95`
- `src/cadrumo/tests/test_worker_count_hook.py:35-153`
- `src/cadrumo/tests/test_every_test_module_is_collectable.py:35-258`
- `src/cadrumo/tests/test_monkeypatch_inventory.py:312-443`
- `src/cadrumo/llm/conftest.py:10-28`
- `src/cadrumo/adapters/outbound/llm/conftest.py:10-28`
- `src/cadrumo/application/modelo/tests/conftest.py:12-20`
- `src/cadrumo/application/modelo/tests/_file_flow_support.py:265`
- Fixture census command: AST parse of `rg --files -g '*.py' -g '!src/cadrumo/_data/**' src dev packaging conftest.py`, selecting functions decorated by `fixture` or `pytest.fixture` and emitting decorator name, scope, and autouse keywords.
