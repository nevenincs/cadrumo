---
tags:
  - '#plan'
  - '#aeat-restructure'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - '[[2026-04-30-aeat-restructure-adr]]'
  - '[[2026-04-30-aeat-restructure-research]]'
---



# `aeat-restructure` execution plan

> **Historical execution plan.** This plan records the pre-cutover
> strategy, including planned shim verification and an `import-linter`
> gate. The rollout outcome superseded those parts with a hard
> cutover: no root re-export layer was retained, and `import-linter`
> is not the current quality gate for ordinary delivery. See the
> 2026-05-01 phase summary and ADR Outcomes section for current state.

## Overview

This plan executes the domain-aligned restructure of `src/aeat/` defined
in the `aeat-restructure` ADR (`status: accepted — execution-ready`).
The ADR specifies the destination shape, the import-boundary contract,
the carve-out registry, the 15 acceptance criteria, the abort/rollback
mechanic, the transition mechanic, the decision authority, the public-
surface table, and the dead-code phasing. This plan does not restate
those decisions — it serialises them into an autonomous, monotonic
sequence of 15 steps and bounds the only invariants that must hold
across them. Architectural detail defers to the ADR; per-module audit
findings defer to the research doc.

The plan is structured for autonomous execution by subagents without
project-owner gate checkpoints.
Subagents own the per-step code reviews, tool selection, audit depth,
and report format. The plan binds outcomes, the disposition framework
for findings, the import-boundary contract, the autonomous gate logic, the
semver impact rules, the abort criteria, the acceptance criteria, and
the vault-corpus tier gating — and nothing else.

## Source artefacts (sources of truth)

- ADR: `[[2026-04-30-aeat-restructure-adr]]` — destination layout,
  import-boundary contract, carve-out registry, 15 acceptance criteria,
  abort/rollback, transition mechanic, decision authority, public-
  surface table, dead-code phasing, monolithic-split planning.
- Research: `[[2026-04-30-aeat-restructure-research]]` — per-module
  audit findings (audits 1–22), domain map + heat map, vault-corpus
  contradictions (Tier 1–4), decision-grounding audit, online research
  validation, layered-architecture violations consolidated, project
  conventions surfaced, dead-code workstream verification.

Throughout this plan, ADR sections are cited by name (e.g. "per ADR
Import-boundary enforcement section") and research-doc sections are
cited by their heading (e.g. "per research doc Layered-architecture
violations consolidated"). Detail not present in this plan is by
design deferred to those artefacts.

## Critical design framing

### Fully autonomous — no human-in-the-loop

**The pipeline runs end-to-end without project-owner gates.** Every
decision that previously required human sign-off is replaced by an
audit-grounded autonomous rule. Audits and research firm up
everything that remains uncertain; subagents make the calls.

This applies to all 16 steps — there are no project-owner gate points.
Specifically:

- **ADR lock-in** (Step 0): the 2 outstanding boundary items are
  resolved by audit-grounded subagent decisions, not owner sign-off.
- **Freeze trigger** (Step 6): the freeze begins automatically when
  Step 5 tooling-prep audits clean.
- **Acceptance + semver + merge** (Step 8): pipeline evaluates the 15
  acceptance criteria; ALL green → merge with rule-based semver bump.
  ANY red → halt + diagnostic. No override path.
- **Abort** (any step): when a halt-trigger fires (CI > 30% failure,
  72h cumulative freeze, coverage floor breach, etc.), revert is
  automatic. No owner invocation required.
- **Historical shim removal model** (post-Step 14, planned): this was
  superseded by the delivered hard cutover. No root compatibility
  re-export layer was retained, so no shim-removal PRs are scheduled.
- **Milestone close** (Step 15): pipeline closes EPIC + milestone
  autonomously when Step 14 audits clean.

### Subagent authority

Subagents own the code reviews at every step. The plan describes
outcomes, not paths — subagents pick the tool (regex sweep vs deep AST
scan vs Explore agent vs `vaultspec-code-reviewer` persona vs other),
the report format (table, prose, JSON ledger), and the audit-pass count
(one or several per step) appropriate for the case in front of them.
The plan does NOT prescribe these details.

### Three-disposition matrix (every finding gets one)

Every finding produced by a subagent — whether from a code review, an
audit pass, or a sanitization sweep — is classified as exactly one of:

| Disposition | When to use | Subagent action |
| --- | --- | --- |
| **FIX** | Small + in-scope for the current step's PR | Apply the edit in the same PR/commit |
| **FILE** | Legitimate concern but out-of-scope for the current step | Open a new GitHub issue (`gh issue create`) with full context, link the issue from the exec record |
| **STRIKE** | The comment, reference, or marker no longer applies | Remove or update the comment/reference; record the strike in the exec record |

The codebase contains references to stubs, work-in-progress, and stale
PR/issue numbers. Every such reference is verified and addressed under
this matrix: subagents either fix it in place, file a follow-up issue,
or strike the stale reference. Subagents have FULL authority for
fix-in-place + issue-filing within the per-step PR scope.

### Hard invariants (the only things this plan binds)

These invariants are non-negotiable and apply across every step.
Everything else is subagent judgment.

- **Layered import-boundary contract** per ADR Import-boundary
  enforcement section: `domain/` MUST NOT import from `adapters/`,
  `application/`, or `entrypoints/`; adapters MUST NOT import from
  each other; `core/` is leaf. The ONLY permitted exceptions are the
  9 `_repository.py` / `_service.py` files in the carve-out registry,
  named explicitly per file (no wildcards).
- **Audit-grounded autonomous decision rules** (replaces ADR Decision
  authority section under the autonomous model): every previously-owner-
  gated decision is replaced by a deterministic rule fired from audit
  findings. Freeze trigger = Step 5 outputs verified clean. Acceptance
  declaration = 15 criteria all green. Semver bump = rule-based per
  public-surface breakage. Rollback = automatic when any halt-trigger
  fires. The planned shim-retention/removal path was superseded by
  hard cutover. CI failures and coverage drops fire halt-triggers
  automatically.
- **Semver impact rules** per ADR Public-surface and semver section:
  minor bump if public surfaces remain compatible; major bump if any
  public surface breaks. Post-ADR shim-less breaks default to major.
  **No override path under the autonomous model** — the rule fires
  deterministically.
- **Abort criteria** per ADR Abort/rollback criteria section: 5 named
  halt triggers (CI > 30% failure across 3 consecutive runs;
  unresolvable circular import beyond 1 working day; marker realignment
  endangers the `live_write` collection-ban; security guardrail
  validation fails at the new location; coverage floor breached) and
  the revert mechanic (single-PR layout move is revertible).
- **Acceptance criteria** per ADR Operational contract / Acceptance
  criteria section: 15 non-waivable items.
- **Vault-corpus tier gating** per ADR Vault-corpus supersession
  section: Tier-2 (security-sensitive path-handling moves) is a HARD
  GATE before the layout-move PR merges. Tier-1 supersedes ride with
  the layout-move PR. Tier-3 inline-updates ship within the same
  milestone. Tier-4 archives are not edited.

### Resume + halt mechanics

- **Step-level resume**: every step persists checkpoint state in
  its exec record. A halted step resumes from its last checkpoint
  without restarting the pipeline.
- **Halt-and-diagnostic**: if a step's audit fails, the step halts
  and surfaces the failure in its exec record. The executing agent
  dispatches a diagnostic subagent. The diagnostic examines the
  failed step's exec record + CI artefacts + audit findings, then
  writes a disposition (RESUME / FIX-AND-RETRY / FIRE-ROLLBACK)
  into a new exec record. The agent reads the disposition and
  fires the next action accordingly — no external triggers
  required.
- **Bounded retry on ambiguous findings** (per ADR Bounded retry):
  audits that return ambiguous findings re-run up to 3 times with
  progressively widened scope. After 3 retries, the pipeline halts
  and writes a "halted-on-ambiguity" exec record. The halted state
  is broken by ONE of: a follow-up audit-subagent re-dispatch with
  explicit override scope, a new commit invalidating the prior
  finding, or a 24-hour timer that fires the rollback halt-trigger
  automatically. There is no infinite-loop risk.
- **Post-Step-8 rollback** (per ADR Post-Step-8 rollback paths):
  if a halt-trigger fires after downstream Steps 9–11 have merged,
  rollback is COMPOUND, not single-PR. Each downstream step has
  its own revert mechanic per the ADR table. The rebase tool's
  reverse-rewrite map (built in Step 5) is the foundation for
  post-Step-9 rollback.
- **No human gates**: there are no points in the pipeline where
  it waits for explicit human sign-off. Ambiguity bottoms out at
  the bounded-retry cap; persistent ambiguity fires rollback.

### Exec record structure

For every step, the exec record lands at
`.vault/exec/2026-04-30-aeat-restructure/step-NN-<slug>.md`. Step 11
(per-module sanitization loop) produces ONE exec record per relocated
module. The phase summary lands at Step 14 close as
`.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-summary.md`.

## Steps

### Step 0 — ADR lock-in (autonomous resolution of remaining items)

- **Gate type**: AUTO
- **Precondition**: ADR and research doc exist at the cited paths.
- **Purpose**: Lock the architectural authority for the rollout.
  Autonomously resolve the two ADR-flagged items that previously
  required project-owner confirmation, by running grounding audits
  that produce binding recommendations.
- **Action**: Two parallel subagent audits produce binding decisions:
  - **Decision 10 (migration-helper retention)** — subagent inspects
    `git log --diff-filter=A` for each `migrate_legacy_*_to_repository`
    function to find when it landed, scans test fixtures for what
    legacy data shape exists, and grep-confirms zero production
    callers. Decision rule: helpers landed > 6 months ago AND zero
    production callers AND test fixtures cover the migration path
    → **DELETE** in Phase 2. Otherwise → **RETAIN with TODO(#issue)
    annotation** and file a removal-tracking issue.
  - **Decision 6 (reserved `SchemaSource` enum slots)** — subagent
    greps issues + branches for `PORTAL_HTML_PROBE`, `MANUAL_LLM_DRAFT`,
    `XSD_WIRE` references. Decision rule: any active branch / open
    issue references the slot → **KEEP**. Otherwise → **DELETE**
    with rationale recorded.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-00-adr-lock-in.md`
  recording both audit findings and the resulting decisions. ADR
  amendment commit lands as part of this step (frontmatter or body
  amendment per `vault edit` mechanics).
- **Audit**: Both decisions are recorded in the exec record with
  audit citation (commit-graph evidence, grep results). No remaining
  "uncertain" items in the ADR.
- **Source citation**: ADR Approval gate section; research doc
  Decision-grounding audit (Decisions 6 + 10).

### Step 1 — Pre-move scan (3 sub-passes, surface obvious blockers)

- **Gate type**: AUTO
- **Precondition**: Step 0 complete.
- **Purpose**: Surface anything a deeper audit might have missed that
  would silently break the layout-move PR. This is a defensive sweep,
  not a re-audit.
- **Action**: Subagents run three sub-passes against `src/aeat/`:
  - **Sub-pass 1** — discover dynamic imports, `importlib`, `getattr`-
    based attribute resolution, and entry-point references in
    `pyproject.toml` that the layout-move script must rewrite or that
    the import-linter contract must understand.
  - **Sub-pass 2** — discover any `__init__.py` re-exports that today
    paper over what will become a layered violation (e.g. a domain-
    package init that re-exports an adapter symbol).
  - **Sub-pass 3** — discover any module-level `pytestmark` declarations
    where the existing axis-B marker would land in the wrong destination
    bucket post-move (cross-module test files that cannot be reclassified
    mechanically by destination — these populate the
    "test-marker manual-override list" referenced in the ADR Acceptance
    criteria).
  Each finding is classified FIX / FILE / STRIKE.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-01-pre-move-scan.md`
  with three findings ledgers (one per sub-pass) and a per-item
  disposition.
- **Audit**: All findings have a disposition. The override-list count
  for the layout-move PR is known. No "blocker — cannot dispose"
  findings remain (those would halt the step for owner review).
- **Source citation**: ADR Operational contract / Acceptance criteria
  ("test-marker manual-override list signed off"); research doc
  modules-audited section (override candidates).

### Step 2 — Phase-1 dead-code deletions (standalone PRs, before move)

- **Gate type**: AUTO
- **Precondition**: Step 1 complete.
- **Purpose**: Remove items with zero cross-domain coupling and zero
  dynamic-invocation risk before the layout move, so the move PR is
  smaller and the dead code does not need to be relocated only to be
  deleted afterward.
- **Action**: Subagents ship one standalone deletion PR per item on the
  Phase-1 list (or grouped where two items share a single domain and a
  single test file). Per ADR Dead-code workstream / Phase 1, the items
  are: `auth/_secret_adapters.py` (whole module + colocated test),
  `auth._providers.describe_certificate_provider` (`__all__` removal),
  `filing.utc_now` (`__all__` removal), `llm._FakeAdapter` (`__all__`
  removal), `llm.ProviderRequest` (`__all__` removal), and
  `schema._extractor.py` (whole 27-LOC file). Every PR runs the
  ADR-mandated pre-merge safety check: unrestricted `grep -r '<symbol>'
  src/` (no `--include` filter) to catch dynamic resolution, config
  references, and docstring references. Each PR carries a code review
  applying the FIX / FILE / STRIKE matrix.
- **Output**: One exec record per PR at
  `.vault/exec/2026-04-30-aeat-restructure/step-02-phase1-<item>.md`
  recording the PR number, the pre-merge safety-check evidence, the
  review findings, and the merge link.
- **Audit**: Every Phase-1 item is either merged-as-deleted or has an
  explicit owner override (recorded). `pytest --collect-only` and
  `just test-cov` run clean post-merge. No new GitHub issue filed by a
  subagent during this step is left dangling without an owner.
- **Source citation**: ADR Dead-code workstream / Phase 1 section;
  research doc Dead-code workstream / Confirmed dead code table +
  Audit-grounded action list (en-bloc approvals, DELETE Phase 1 group);
  ADR Acceptance criteria (Dead-code workstream Phase 1 + Phase 2
  deletions complete).

### Step 3 — Layered-violation untangling (prep PRs, before move)

- **Gate type**: AUTO
- **Precondition**: Step 2 complete.
- **Purpose**: Eliminate the existing layered-architecture violations
  before the layout move so the import-linter contract installed in
  Step 5 finds zero violations on day one of the new layout.
- **Action**: Subagents ship one prep PR per violation listed in
  research doc Layered-architecture violations consolidated (7 active
  + 1 false positive already corrected). The recommended resolution
  pattern is named in the research doc per violation; subagents pick
  the implementation. Notable resolutions:
  - `validate_spanish_tax_id` is promoted to `core/identity/`,
    eliminating violations 5 and 6 (the storage `_master_key` NIF
    canary and the sanitizer `_records` synthetic-NIF check) in one
    move.
  - The `verification._verify` and `cli/filing/__init__.py` private-
    bypass imports into `formulas._*` are resolved by promoting the
    needed symbols to the public formulas surface.
  - `casillas` → `aeat.entrypoints.cli` and `profile.assets` → `formulas._rulesets`
    private imports are traced to specific call sites and re-routed to
    public APIs.
  - `filing._review` → `aeat.domain.financial.transactions._repository` is
    rewritten through the public subpackage surface, OR the symbol is
    promoted.
  Each PR carries a code review under the FIX / FILE / STRIKE matrix.
- **Output**: One exec record per violation at
  `.vault/exec/2026-04-30-aeat-restructure/step-03-violation-<n>.md`
  recording the resolution pattern chosen, the PR number, and the
  review findings.
- **Audit**: After this step, an `import-linter`-shaped scan against
  the **current** (pre-move) layout reports zero of the 7 named
  violations remaining. Tests pass.
- **Source citation**: ADR Constraints (live-access gate /
  `LiveSubmitForbiddenError` relocation); research doc Layered-
  architecture violations consolidated section + Subpackage-private
  import boundary violation section + Decision-grounding audit
  Decision 4 + audit-grounded action list (RELOCATE block).

### Step 4 — Tier-2 security-audit prep (HARD GATE before move)

- **Gate type**: AUTO
- **Precondition**: Step 3 complete.
- **Purpose**: Satisfy the ADR's hard pre-merge gate that
  security-sensitive path-handling guardrails are revalidated AT THEIR
  NEW LOCATION before the layout-move PR can merge. Without this step,
  the silent move of a security guardrail is a regression.
- **Action**: Subagents:
  - Author or extend an explicit guardrail unit test that exercises
    the path-resolution behaviour cited in
    `audit/2026-04-17-path-handling-safety-review-audit.md` and
    `audit/2026-04-30-secure-persistence-foundation-final-security-audit.md`
    (the `resolve_record_json_path` boundary).
  - Stage the test so it can run against the new `core/paths.py`
    location once the layout move lands — the test ships in the
    layout-move PR's CI, gating the merge.
  - Inline-update both audit documents in place to reference the new
    path. Inline-updates ship in the same PR as the layout move; the
    test ships there too.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-04-tier2-security-prep.md`
  recording the guardrail test source, the inline-update diffs, and
  evidence the test fails against a hypothetical bypass and passes
  against the canonical path.
- **Audit**: The guardrail test is committed to the layout-move PR
  branch; CI runs it and it passes against the new path. Both audit
  documents have inline updates queued in the same PR. **HARD GATE**:
  the layout-move PR (Step 7) cannot merge until both conditions hold.
- **Source citation**: ADR Vault-corpus supersession section (Tier 2
  treatment, "Revalidated means" definition); ADR Acceptance criteria
  ("Security-audit guardrails validated at new locations"); research
  doc Vault-corpus contradictions / Tier 2 inventory.

### Step 5 — Tooling prep (rebase script, contracts, smoke test, type-checker, packaging tests)

- **Gate type**: AUTO
- **Precondition**: Step 3 complete (Step 4 ships in the layout-move PR but its prep work runs in parallel with Step 5 — this step does not wait for Step 4 to ship).
- **Purpose**: Prepare every piece of mechanical and verifiable tooling
  the layout-move PR depends on. By the end of this step, the
  layout-move PR is a mechanical merge of the rewrite map plus
  configuration adjustments — no design decisions remain.
- **Note**: several Step-5 artefacts are **net-new build work**, not
  ports — the migration-script test fixture, the produce → verify →
  export end-to-end smoke test, the packaging verification job, the
  import-linter contract, the type-checker baseline, and the historical
  shim-verification subroutine (later superseded by hard cutover) do
  not currently exist in the planning baseline. The executing
  agent applies the autonomous decision rules itself (per ADR
  Autonomous decision rules); no external workflows or schedulers
  are built. Building the listed artefacts is multi-day work;
  allocate appropriately.
- **Action**: Subagents produce, in any order they prefer:
  - **Mechanical rebase script** — walks an arbitrary diff and rewrites
    import paths from old to new per the ADR-defined rewrite map. The
    script ships with a test fixture exercising every kind of import
    the project actually uses: relative imports (`.module`,
    `..sibling`), `TYPE_CHECKING` blocks, star imports, and dynamic
    `importlib.import_module` calls. The script also handles the
    public-surface rewrites and any historical re-export-shim planning
    inventory.
  - **Static import-boundary diagnostic** — originally planned as an
    `import-linter` contract committed at the project root. The
    delivered hard cutover keeps the carve-out registry documented,
    but `import-linter` is not the current quality gate for ordinary
    delivery.
  - **End-to-end behavioural smoke test** — at least one CI integration
    test exercises the full `produce → verify → export` pipeline on a
    synthetic transaction set. This is a hard requirement, not a
    nice-to-have: structural import-resolution alone is insufficient
    proof of restructure correctness.
  - **`mypy` and/or `pyright` configuration** — per the project's
    existing static-type tooling, configured against the new layout.
    The configuration is wired into CI; zero-error baseline is a hard
    gate.
  - **Packaging verification** — a CI job that runs `pip install -e .`,
    `pip install dist/*.whl`, and a post-install
    `python -c "from aeat.adapters.outbound.aeat.export import ..."`
    smoke check. Verifies the new sub-paths are exposed by the wheel.
  - **Historical shim-verification subroutine** — planned before the
    hard cutover as a semver precondition. It was superseded when the
    delivered migration rewrote callers to canonical paths and retained
    no root compatibility re-export modules.
  - **Reverse-rewrite map** — the rebase script emits BOTH a forward
    map (old → new) AND a reverse map (new → old). The reverse map
    is the foundation of post-Step-9-merge rollback per the ADR
    Post-Step-8 rollback paths section.
  Each artefact is reviewed under the FIX / FILE / STRIKE matrix.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-05-tooling-prep.md`
  recording the artefacts, where they are committed, and the CI wiring.
  Artefacts are committed to a long-lived branch ready to fast-forward
  into the layout-move PR.
- **Audit**: Each tooling artefact is independently runnable and
  passes against a synthetic input (rebase script against a fixture
  diff; boundary diagnostics against the pre-move layout to baseline;
  smoke test against pre-move pipeline; type-checker against pre-move
  source for baseline; packaging test against pre-move build).
- **Source citation**: ADR Acceptance criteria (Static import-boundary
  enforcement; End-to-end behavioural smoke test; Type-checker clean
  run; Migration-script correctness test fixture; Packaging
  verification); ADR Transition mechanic (one-shot mechanical rebase
  tool); ADR Implementation / Import-boundary enforcement section.

### Step 5.5 — Dry-run / sandbox validation (full pipeline rehearsal)

- **Gate type**: AUTO
- **Precondition**: Step 5 complete; all tooling artefacts committed
  to the long-lived restructure branch.
- **Purpose**: Validate the complete layout-move + acceptance-gate
  pipeline against a forked branch in a sandbox before the real
  Step-7 PR runs. A change of this magnitude (~50 modules moved,
  6+ monoliths split, hundreds of import rewrites) cannot be bet
  without a rehearsal.
- **Action**: The executing agent (or a subagent dispatched by it):
  - Creates a sandbox branch off `main` (named `restructure-dry-run`).
  - Runs the rebase script against the sandbox branch. Verifies the
    diff matches the ADR-defined rewrite map.
  - Runs the boundary diagnostic against the sandbox state. Expects no
    unexplained violations.
  - Runs the end-to-end produce → verify → export smoke test against
    the sandbox state. Expects green.
  - Runs the type-checker (mypy / pyright) against the sandbox state.
    Expects zero errors.
  - Runs the packaging verification against the sandbox state.
    Expects green.
  - Historical plan only: would have run shim verification. The
    delivered hard cutover instead verifies canonical imports directly.
  - Applies the reverse-rewrite map against the sandbox to confirm
    rollback symmetry.
  - DOES NOT merge the sandbox branch — it is verification-only.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-05-5-dry-run.md`
  recording the sandbox branch SHA, the diff size, the per-check
  pass/fail results, and any tooling adjustments needed for Step 7.
- **Audit**: All 7 sandbox checks pass. Sandbox branch is closed
  (deleted) after recording the results — sandbox is not promoted
  to the layout-move PR; Step 7 produces the canonical PR fresh
  using the validated tooling.
- **Failure mode**: any sandbox check failing → Step 5.5 halts and
  surfaces the failure. The agent dispatches a diagnostic subagent
  that decides RESUME / FIX-AND-RETRY / FIRE-ROLLBACK per the ADR
  Halt-then-resume mechanic.

### Step 6 — Freeze announced (autonomous trigger)

- **Gate type**: AUTO
- **Precondition**: Steps 0–5.5 complete; the dry-run validation passed
  green; the layout-move PR is staged with all tooling, contracts, and
  pre-merge gates ready to run.
- **Purpose**: Open the brief incompatibility window during which the
  layout-move PR merges. Coordinate parallel agent slots to pause new
  branch creation off pre-move main.
- **Action**: Pipeline triggers freeze automatically when Step 5
  outputs are committed and verified. PM layer (autonomous
  scheduling) pauses the parallel agent slots (up to 6). Open PRs
  enumerated by `gh pr list` are auto-labelled
  `needs-rebase-post-restructure`. Freeze timer starts; targets
  less than 24 hours and extends in 12-hour increments per ADR
  policy. **Auto-rollback rule**: cumulative freeze longer than 72
  hours triggers automatic rollback per the abort criteria.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-06-freeze.md`
  recording the freeze start timestamp, the agent-slot pause
  confirmation, and the pre-move open-PR list with
  `needs-rebase-post-restructure` labels.
- **Audit**: Step 5 outputs committed AND verified clean → freeze
  trigger fires. Agent-slot pause logged. Open-PR list captured.
- **Source citation**: ADR Transition mechanic (Freeze window + Freeze
  extension policy + Agent-slot orchestration + Open PRs); ADR Decision
  authority (Calling the freeze before the layout-move PR).

### Step 7 — Layout-move PR (single mechanical relocation)

- **Gate type**: AUTO
- **Precondition**: Step 6 complete; freeze is in effect.
- **Purpose**: Execute the single mechanical PR that relocates every
  module to its destination per the ADR Implementation section, with
  every required contract, configuration update, and pre-merge gate
  attached. This PR is the layout move; nothing else rides with it
  except items the ADR explicitly couples to it (Tier-1 supersedes,
  Tier-2 inline-updates, marker rename, Phase-2 dead-code that rides
  with a relocated module).
- **Action**: A single subagent (or small subagent team) ships the PR.
  The mechanical rebase script from Step 5 produces the import-rewrite
  diff. The PR additionally:
  - Adds the carve-out registry's per-file `ignore_imports` entries to
    the boundary diagnostic.
  - Rewrites public-surface consumers to canonical layered modules.
    The planned root re-export shim layer and deprecation lifecycle were
    superseded by hard cutover.
  - Inline-updates the configuration files cited in ADR Configuration
    files affected (`pyproject.toml` coverage / mypy / pytest paths;
    pre-commit configs; `.mcp.json`; `justfile`; `.gitignore`; CI
    workflow path-scoped steps).
  - Performs the test-marker realignment per ADR Test-marker
    realignment table (`domain_inbound`, `domain_model`,
    `domain_persistence`, `domain_outbound`, `domain_export` sub-marker,
    `domain_application`, `domain_core`).
  - Reclassifies `domain_local_state` test files mechanically by their
    containing module's destination. Manual overrides are limited to
    the explicit list signed off in Step 0/1 and per ADR Acceptance
    criteria.
  - Applies Tier-1 supersedes (frontmatter `superseded_by:` additions)
    on the two core canonical docs cited in research doc Vault-corpus
    contradictions / Tier 1.
  - Applies Tier-2 inline-updates and the Step-4 guardrail test
    (HARD GATE).
  - Applies Phase-2 dead-code deletions that ride with a relocated
    module per ADR Dead-code workstream / Phase 2 (4 empty subpackages,
    `_submitters/` tombstone, `fetch_justificante_pdf`
    `NotImplementedError` raise, selected Protocol cleanup in `sync`,
    and deletion of the obsolete lock-error fixture path).
  PR-time code review applies the FIX / FILE / STRIKE matrix.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-07-layout-move.md`
  recording the PR number, the rewrite-map evidence, every gate's CI
  result, the marker-rename diff, the override-list resolution, the
  public-surface rewrite evidence, and the configuration-file diffs.
  The PR DOES NOT merge
  in this step — Step 8 applies the autonomous acceptance gate and
  merge decision.
- **Audit**: Every ADR Acceptance criteria item that applies to the
  layout-move PR has CI evidence: `python -c "import aeat"` succeeds;
  `pytest --collect-only` runs without `ImportError`; coverage floor
  ≥ 60%; boundary diagnostics report no unexplained violations; smoke test passes;
  `mypy` / `pyright` reports zero errors; packaging test passes;
  Tier-2 guardrail test passes; manual-override list zero-length OR
  signed off; Tier-1 supersedes shipped; configuration files updated;
  marker-rename complete with no test in a wrong-marker state.
- **Source citation**: ADR Implementation section (whole); ADR
  Public surface and semver section; ADR Test-marker realignment
  section; ADR Vault-corpus supersession section (Tier-1 + Tier-2
  treatment); ADR Configuration files affected; ADR Dead-code
  workstream / Phase 2; research doc Vault-corpus contradictions /
  Tier 1 + Tier 2.

### Step 8 — Acceptance-criteria evaluation + semver bump + merge (autonomous)

- **Gate type**: AUTO
- **Precondition**: Step 7 complete; the layout-move PR is green on
  every gate.
- **Purpose**: Pipeline evaluates the 15 ADR acceptance criteria
  against the Step-7 PR; applies the semver bump rule deterministically;
  merges if all criteria pass.
- **Action**: Subagent runs the acceptance-criteria checklist
  against the PR:
  1. Imports resolve under the new layout.
  2. Coverage floor maintained (`just test-cov` ≥ 60%).
  3. Static import-boundary diagnostics clean; `import-linter` is not
     the current ordinary-delivery gate.
  4. Vault contradiction list per-tier completion: T1 supersedes
     shipped, T2 validated and inline-updated.
  5. Test markers fully realigned.
  6. `domain_local_state` test files reclassified by destination.
  7. Public-surface decisions executed (canonical rewrite or documented
     break).
  8. Configuration files updated.
  9. Security-audit guardrails validated at new locations.
  10. Empty placeholder subpackages deleted.
  11. Top-5 monolithic split designs folded into the ADR (already
      satisfied per ADR Approval gate).
  12. Dead-code workstream Phase 1 + Phase 2 deletions complete (Step
      2 + Step 7 contributions).
  13. End-to-end behavioural smoke test passes.
  14. Type-checker clean run (`mypy` / `pyright` zero errors).
  15. Migration-script correctness test fixture passes; packaging
      verification passes; manual-override list zero-length OR audit-
      grounded sign-off.
  **Decision rule (deterministic, no override)**:
  - All 15 criteria green → declare acceptance, apply semver bump,
    merge.
  - Any criterion red → halt, surface failure in exec record, abort
    pipeline (no auto-retry; failure is signal, not noise).
  - Semver: compatible public-surface outcome → minor bump. Any public
    surface break → major bump. Post-ADR shim-less break defaults
    major. **No override path** (the ADR Decision Authority section's
    "owner override" path is removed under the autonomous
    model; the rule fires deterministically from audit findings).
  CHANGELOG entry generated mechanically from the public-surface table.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-08-merge-and-bump.md`
  recording the acceptance-criteria checklist with per-item status, the
  semver bump call (with rule-trace showing how the rule fired), the
  CHANGELOG entry, and the merge timestamp.
- **Audit**: All 15 acceptance-criteria items audit-grounded green.
  Semver bump rule applied deterministically. Merge complete.
- **Source citation**: ADR Operational contract / Acceptance criteria
  (15 items); ADR Public surface and semver (semver impact rules,
  post-ADR break policy); ADR Decision authority (declaring acceptance
  criteria met, authorising semver bump).

### Step 9 — Lift freeze + rebase tool against in-flight branches

- **Gate type**: AUTO
- **Precondition**: Step 8 complete; layout-move PR merged.
- **Purpose**: Reopen the project to parallel work and migrate any
  pre-move branches to the new layout via the mechanical rebase tool
  shipped in Step 5.
- **Action**: PM layer lifts the freeze. The mechanical rebase tool
  runs against every open PR labelled `needs-rebase-post-restructure`.
  PRs that the tool rebases cleanly are unblocked. PRs that the tool
  cannot rebase cleanly are flagged for manual resolution and assigned
  back to the originating contributor or agent slot. Agent slots
  resume normal operation.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-09-lift-freeze.md`
  recording the rebase-tool run results per PR (clean / flagged), the
  agent-slot resume confirmation, and the freeze duration.
- **Audit**: Every previously-frozen PR is either rebased clean,
  flagged for manual resolution with an owner, or closed. Agent slots
  are unblocked. No PR sits in `needs-rebase-post-restructure` limbo
  without an owner.
- **Source citation**: ADR Transition mechanic (In-flight branches +
  Open PRs).

### Step 10 — Phase-2 dead-code deletions (loose ends)

- **Gate type**: AUTO
- **Precondition**: Step 9 complete.
- **Purpose**: Land any Phase-2 dead-code deletions that the Step-7 PR
  did not pick up (because they did not ride with a specific module
  move, or because they were deferred for a separate review). This
  step closes the dead-code workstream.
- **Action**: Subagents review the Phase-2 list against what merged in
  Step 7, identify any items still outstanding, and ship one PR per
  item (or grouped per the audit's recommendation). Items include
  any of the following not already merged: 4 hollow Protocol stubs in
  `sync` (`LLMClient`, `LLMRequest`, `ManualRulesLoader`,
  `SchemaLoader`), obsolete test-only concrete error fixtures, the
  duplicate `default_schema_provider` in
  `filing/_builders/_modelo_130_schema.py`, and the 3 reserved
  `SchemaSource` enum members per Step 0 Decision 6 (`PORTAL_HTML_PROBE`,
  `MANUAL_LLM_DRAFT`, `XSD_WIRE`). The **5 migration helpers**
  (`migrate_legacy_submissions_to_repository`,
  `migrate_legacy_amendments_to_repository`,
  `migrate_legacy_filing_history_to_repository`,
  `migrate_legacy_drafts_to_repository`,
  `migrate_legacy_justificantes_to_repository` — count corrected from
  the prior "3" by Step 0 audit) are NOT deleted in this step per
  Step 0 Decision 10 (`RETAIN with TODO(#477)`); they remain in tree
  with annotations and are revisited at the 2026-10-27 retention
  expiry tracked in `#477`. Each PR runs the unrestricted
  `grep -r '<symbol>' src/` pre-merge safety check. Code review
  applies the FIX / FILE / STRIKE matrix.
- **Output**: One exec record per PR at
  `.vault/exec/2026-04-30-aeat-restructure/step-10-phase2-<item>.md`.
- **Audit**: Phase-2 list is fully closed. Every item is either
  merged-as-deleted, merged-as-resolved, or has an explicit owner
  override (recorded). `pytest --collect-only` and `just test-cov`
  run clean post-merge.
- **Source citation**: ADR Dead-code workstream / Phase 2; research
  doc Dead-code workstream / Confirmed dead code table + Audit-grounded
  action list (DELETE Phase 2 group); research doc Decision-grounding
  audit Decision 10 (migration-helper retention window).

### Step 11 — Per-module sanitization (canonical AUTO loop)

- **Gate type**: AUTO LOOP (one sub-iteration per relocated module)
- **Precondition**: Step 10 complete.
- **Purpose**: Walk every relocated module and remove the dev-process
  metadata, stale PR/issue references, WIP comments, and other
  non-architectural sediment that accumulated during the parallel
  delivery of the prior milestone. Apply the FIX / FILE / STRIKE
  matrix to every finding. This is the longest and most procedural
  step; subagents iterate one module at a time.
- **Action**: For every module relocated by Step 7, a subagent runs:
  1. **Audit pass** — scan the module's source tree (and colocated
     tests) for the patterns enumerated in the sanitization rules
     below.
  2. **Classify each finding** as FIX / FILE / STRIKE per the
     disposition matrix.
  3. **Apply FIX + STRIKE** dispositions in a per-module PR.
  4. **Open issues** (`gh issue create`) for FILE dispositions, link
     them from the module's exec record.
  5. **Code-review pass** on the resulting PR. The reviewer applies
     the disposition matrix to the review's own findings (recursive
     application is allowed; the loop terminates when the PR review
     surfaces zero findings or only FILE-disposition findings).
  6. **Merge** + record exec entry.

  **Sanitization rules (subagent finding-classification reference)**:

  *HIGH-CONFIDENCE PURGE* (pattern-based, low false-positive risk):
  - `wave\s*\d+` (e.g. "Wave 2"), `wave-\d+`, `wave_\d+`.
  - `phase\s*\d+` (e.g. "Phase 3").
  - `cluster\s*[a-z]` (e.g. "#305 cluster A").
  - "added in PR #", "ships in PR #", "via PR #".
  - "tracking #\d+" inside docstrings (distinct from `# TODO(#nnn):`
    inline comments which are keep-conditional — see medium-confidence
    rules).
  - Comment blocks "removed in #" / "deleted code".
  - Author tags / personal dates in module headers.

  *MEDIUM-CONFIDENCE — PER-OCCURRENCE CLASSIFICATION*:
  - Bare `#\d+` references in docstrings — context-dependent.
    Subagent classifies per occurrence.
  - `TODO(#\d+)` — if the issue is closed, STRIKE; if the issue is
    open and the TODO is still actionable, KEEP; if the issue is open
    but irrelevant to the sanitised module, STRIKE the TODO and close
    the issue with a comment explaining the closure.
  - "Issue #\d+" in module docstrings — keep ONLY if naming a stable
    feature ID; STRIKE if it names a delivery-cadence reference.

  *KEEP UNCONDITIONALLY* (legitimate references):
  - Statutory citations (LIRPF, IRPF, RD nnn/yyyy, Ley nn/yyyy).
  - BOE references, casilla codes, modelo codes (`Modelo 100`,
    `Modelo 130`, etc.).
  - Article references (`art. 23.1.f`, etc.).
  - Spanish AEAT-canonical vocabulary (`borrador`, `declaracion`,
    `justificante`, `sede`, `casillas`, `modelos`).

  *EDGE-CASE GUIDANCE — when uncertain, FILE not STRIKE*: subagent
  judgment must default to **conservative**. If a finding is
  ambiguous (e.g. a `#nnn` reference that could be either a stable
  feature ID or a delivery-cadence reference; a `wave` mention that
  might refer to project Track-A/Track-B language rather than dev
  cadence; a TODO whose linked issue is closed but whose code path
  still produces wrong output), the subagent FILEs the finding
  (preserves the comment, opens a tracking issue) rather than
  STRIKEs it. STRIKE is reserved for findings the subagent can
  classify with full confidence. **When in doubt: FILE, not STRIKE.**

  Subagents pick the tool — regex sweep, AST scan, semantic search,
  Explore agent, `vaultspec-code-reviewer` — depending on the module's
  size and complexity. Subagents do NOT batch multiple modules into
  one PR; one module per PR is the rule (the per-module exec record
  depends on it).
- **Output**: One exec record per relocated module at
  `.vault/exec/2026-04-30-aeat-restructure/step-11-<module-slug>.md`.
  Each record names the module, the audit pass results, the
  per-finding disposition, the PR number, the GitHub issues filed for
  FILE dispositions, and the code-review verdict.
- **Audit**: Every relocated module has exactly one Step-11 exec
  record. Every record's PR is merged or has an explicit halt + owner
  review. No record contains an unclassified finding. Issues filed for
  FILE dispositions are visible on the project board and linked from
  the record.
- **Source citation**: User instruction on dev-process-metadata
  removal (memory: no wave/phase numbering in source code); research
  doc Modules audited section (per-module destinations); ADR
  Implementation section (the relocated module set).

### Step 11.5 — Sanitization rollup checkpoint

- **Gate type**: AUTO
- **Precondition**: Step 11 complete for every relocated module.
- **Purpose**: Consolidate the per-module sanitization ledgers into a
  single rollup before Step 12 begins. Step 14 final review cannot
  meaningfully audit ~40 separate per-module passes without a
  consolidated checkpoint; the rollup is the bridge.
- **Action**: A subagent walks every Step-11 exec record and produces
  a rollup document with:
  - Per-module summary: PR number, FIX/FILE/STRIKE counts, links to
    filed issues, code-review verdict.
  - Aggregate counters: total LOC purged, total issues filed, total
    strikes applied, modules with zero findings, modules with halt
    records.
  - Issue-board cross-check: every FILE-disposition issue is
    visible on the project board, has appropriate labels, and is
    triaged into a follow-up milestone.
  - Anomaly highlight: modules with disproportionate finding counts,
    halt records, or unmerged PRs.
- **Output**:
  `.vault/exec/2026-04-30-aeat-restructure/step-11-5-sanitization-rollup.md`
  containing the consolidated ledger.
- **Audit**: Every relocated module has a row in the rollup. Every
  Step-11 exec record is referenced. No module is missing from the
  rollup. Aggregate counters are arithmetically consistent with the
  per-module records.

### Step 12 — Tier-3 vault inline-updates

- **Gate type**: AUTO
- **Precondition**: Step 11 complete (or substantially complete; this
  step does not block on every per-module Step-11 PR merging — the
  Tier-3 inline-updates target the vault corpus, not the source).
- **Purpose**: Land the Tier-3 inline-updates on every authoritative
  `.vault/` document that contains stale path / marker / module-name
  references but is still authoritative on its topic. This is a
  release-completion gate per the ADR, not a hard gate on the
  layout-move PR.
- **Action**: Subagents iterate the Tier-3 inventory in research doc
  Vault-corpus contradictions / Tier 3 — inline-update needed
  section. The inventory is grouped by cluster (test markers,
  roadmap snapshot, submission cluster, models cluster, errors
  cluster, logging cluster, MCP cluster, PDF-import cluster,
  subpackage-inventory snapshots). Each cluster is one PR (or split
  if the diff is large). Documents are inline-updated in place — the
  topic decision is preserved; only the stale references are rewritten
  per the new layout. Code review applies the FIX / FILE / STRIKE
  matrix.
- **Output**: One exec record per cluster at
  `.vault/exec/2026-04-30-aeat-restructure/step-12-tier3-<cluster>.md`.
- **Audit**: Every Tier-3 document has been opened, scanned for stale
  references, inline-updated where needed, and re-saved through
  `vault edit` (no hand-authored frontmatter changes). The full
  vault-corpus contradiction list is at 100% per-tier completion: T1
  supersedes shipped (Step 7), T2 validated + inline-updated (Step 4
  + Step 7), T3 inline-updates landed (this step), T4 archive
  untouched.
- **Source citation**: ADR Vault-corpus supersession section (Tier 3
  treatment); ADR Acceptance criteria (Vault contradiction list at
  100% per-tier completion); research doc Vault-corpus contradictions
  / Tier 3 inventory.

### Step 13 — Missing-implementation full-coverage audit + issue filing

- **Gate type**: AUTO
- **Precondition**: Step 12 complete (or running in parallel; the
  audit does not depend on Tier-3 vault edits).
- **Purpose**: Walk the new layout and surface every missing
  implementation, hard gap, coverage gap, casilla gap, stub gap, and
  placeholder gap. The output is a bulk issue-filing pass — not new
  work in this milestone, but the next milestone's input plan.
- **Action**: Subagents scan the new layout for the gap categories
  enumerated below. Every gap → one new GitHub issue filed by the
  subagent (`gh issue create`) with full context: file:line of the
  gap, the gap category, a sketch of the required implementation, the
  Kent capability the gap blocks (per project mandate), and a
  reference to the modelo / casilla / pipeline stage in the relevant
  coverage matrix.

  **Gap categories**:
  - **Hard gap**: production-reachable `raise NotImplementedError` —
    a code path is wired but not implemented.
  - **Coverage gap**: a modelo declared in `domain/modelos/` is
    missing from `domain/formulas/_rulesets/` for a year covered by
    the project's modelo-coverage matrix.
  - **Casilla gap**: a casilla declared in the catalogue but no
    formula or input-only declaration exists.
  - **Stub gap**: an empty function body with no docstring AND no
    caller (true dead — STRIKE) versus an empty function body with a
    caller (genuine stub — FILE).
  - **Placeholder gap**: an enum value reserved but actively rejected
    by a validator (e.g. `SchemaSource.PORTAL_HTML_PROBE`).

  The disposition matrix applies: STRIKE for true dead, FIX for
  trivial cases (a missing one-line implementation that is unambiguous
  per existing context), FILE for everything else. The bulk of the
  output is FILE.

  **Batched-issue filing rule** (anti-spam guard): individual issue-
  per-gap filing would flood the project board (potentially dozens
  of missing-modelo / missing-casilla issues at once). Instead, the
  subagent BATCHES findings by category before filing:
  - **One umbrella issue per gap category** with all findings of
    that category as a checklist (e.g. "Missing modelo
    implementations: M200/2024, M200/2026, M202/2024, M202/2026,
    ...").
  - **Per-category umbrella issues** are labelled with the gap
    category, the affected milestone target (next milestone or
    backlog), and the originating audit (`audit-grounded`,
    `restructure-step-13`).
  - **Hard gaps** (production-reachable NotImplementedError) get
    INDIVIDUAL issues — not batched — because each is a real
    Kent-blocking bug.
  - **The umbrella-issue + individual-issue split** keeps the
    project board readable while preserving traceability.

  Maximum issues filed by Step 13: **5 umbrella issues** (one per
  gap category) + N individual issues for hard gaps (typically
  small N).
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-13-missing-impl-audit.md`
  recording the audit methodology (tool choice, scan depth), the gap
  inventory by category, the per-gap disposition, and the GitHub
  issue numbers filed.
- **Audit**: Every gap has a disposition. Every FILE-disposition gap
  has a GitHub issue link recorded. The issue board reflects the
  filed issues (visible to the next milestone planner).
- **Source citation**: User instruction on missing-implementation
  flagging; research doc Decision-grounding audit (Decision 6 reserved
  `SchemaSource` enum slots); project mandate (Kent-observable
  acceptance criteria); coverage matrices cited in the project
  mandate.

### Step 14 — Final post-migration code review + ADR closure

- **Gate type**: AUTO
- **Precondition**: Steps 11–13 complete.
- **Purpose**: Run a final post-migration code-review pass over the
  full new layout, surface any sediment the per-module Step-11 sweeps
  missed, and close the ADR by appending an "outcomes" section
  pointing at this plan's exec records.
- **Action**: A subagent (or small subagent team) runs:
  - A `vaultspec-code-reviewer`-class pass over the full new layout,
    looking for patterns Step 11 might have missed at the seams
    between modules — cross-module duplications, residual private-
    bypass imports the import-linter contract did not catch, missing
    or misplaced public-surface declarations.
  - A vault hygiene pass via `vaultspec-core vault check all`,
    addressing any drift surfaced.
  - The phase-summary write at
    `.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-summary.md`
    via `vaultspec-core vault add` mechanics. The summary references
    the ADR, the research doc, and every Step exec record by wiki-link.
  - An ADR amendment (or a follow-up addendum entry, depending on
    project convention) recording the rollout's actual outcomes:
    semver bump landed, no active shim-retention schedule, dead-code
    totals removed, issues filed by Step 13, override list resolution.
  Findings classified under the FIX / FILE / STRIKE matrix.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-14-final-review.md`
  + the phase summary at
  `.vault/exec/2026-04-30-aeat-restructure/2026-04-30-aeat-restructure-summary.md`.
- **Audit**: `vaultspec-core vault check all` runs clean. The ADR
  contains an outcomes section. The phase summary exists and
  wiki-links every step record. Final review surfaces zero
  unclassified findings.
- **Source citation**: ADR References section; project mandate
  (vaultspec pipeline phase 5 — Verify, via `vaultspec-code-review`
  skill); the vaultspec workflow Documentation Hierarchy.

### Step 15 — Milestone close (autonomous)

- **Gate type**: AUTO
- **Precondition**: Step 14 complete.
- **Purpose**: Pipeline closes the restructure milestone autonomously
  once Step 14 audits green and triages Step-13-filed issues into the
  next milestone. No shim-removal work is queued because the delivered
  hard cutover retained no root compatibility re-export layer.
- **Action**: Subagent reads phase summary and confirms the 15
  acceptance criteria still hold (no regression since Step 8).
  Subagent posts milestone-close announcement via `gh milestone close`,
  closes EPIC #475 via `gh issue close --reason completed`, and
  records that no shim-removal schedule exists. Step-13-filed issues
  are triaged via labels into the next milestone.
- **Output**: `.vault/exec/2026-04-30-aeat-restructure/step-15-milestone-close.md`
  recording the milestone-close trigger, the EPIC closure, the absence
  of a shim-removal schedule, and the next-milestone enqueue.
- **Audit**: Step 14 audits clean → Step 15 trigger fires. Milestone
  closed in the
  project's tracking surface. No outstanding ADR Acceptance criteria
  item is in a regressed state.
- **Source citation**: ADR Decision authority (declaring acceptance
  criteria met); ADR hard-cutover outcome superseding the historical
  shim deprecation contract; ADR References section.

## Parallelization

The plan is **monotonic by design**. Step-level parallelism is bounded
by the named preconditions; intra-step parallelism is at the subagent's
discretion within the FIX / FILE / STRIKE matrix.

Parallelism opportunities:

- Step 2 Phase-1 deletions: each item ships as a standalone PR;
  multiple subagents can ship in parallel (subject to the standard
  per-PR review and the agent-slot cap).
- Step 3 layered-violation untangling: one PR per violation; subagents
  parallelise as agent-slot capacity allows.
- Step 11 per-module sanitization: the canonical loop. One PR per
  module is the rule, but multiple subagents can take different
  modules in parallel. Coordination is via the exec-record write.
- Step 12 Tier-3 cluster updates: one PR per cluster; subagents
  parallelise.

Sequential by design (no parallelism):

- Steps 0, 6, 8, 15 are autonomous control gates — sequential by
  definition.
- Step 4 Tier-2 prep runs strictly before Step 7 layout-move (HARD
  GATE).
- Step 5 tooling prep runs strictly before Step 7 (the layout-move PR
  consumes the tooling).
- Step 7 layout-move is a single PR, single subagent (or small team
  acting as one) — the rewrite must be atomic.
- Step 9 freeze-lift runs strictly after Step 8 merge.

## Verification

Mission success is the **15 ADR acceptance criteria** (Operational
Contract / Acceptance criteria section), all satisfied at Step-8 merge
and re-verified at Step-15 milestone close. The plan does not invent
new success criteria — the ADR's contract is canonical.

Beyond the acceptance criteria, the following operational checks
indicate non-tautological, non-cheatable mission completion:

- The end-to-end behavioural smoke test exercises the full
  `produce → verify → export` pipeline on a synthetic transaction set
  in CI. Structural import-resolution alone is not proof of
  restructure correctness; the smoke test is the load-bearing
  behavioural witness.
- The boundary carve-out registry is grep-able. Any new
  `_repository.py` or persistence-side service in `domain/<name>/`
  introduced post-restructure is either added to the registry by name
  in a follow-up ADR amendment OR moved to `application/<name>/`. The
  registry's escalation policy is the long-term safety net against
  silent carve-out drift.
- The historical shim deprecation contract is inactive. The delivered
  hard cutover retained no root compatibility re-export modules, so
  there are no shim consumers to warn and no deprecation-window cleanup
  milestone to schedule.
- The Step-13 missing-implementation audit produces an explicit issue
  inventory the next milestone can plan against. The audit is a
  surface for the next round of Kent-capability work, not a closure
  of this restructure.
- The Step-15 phase summary cross-references every Step exec record
  via wiki-link. Anyone auditing the rollout has a single entry point
  into the full execution trail.

The honest ceiling on this plan: structural correctness is verifiable;
behavioural correctness depends on the smoke test plus the project's
existing test suite holding green. If the smoke test or the test suite
regresses post-merge, the abort criteria in the ADR Operational
contract apply. Step-level resume + halt-and-notify is the operational
mechanism — there is no auto-retry on audit failures because failures
are signal.
