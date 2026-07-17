---
tags:
  - '#audit'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
related:
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-07-01-import-centralization-research]]'
  - '[[2026-07-01-import-centralization-plan]]'
---

# `import-centralization` audit: `closeout synthesis of the structural code review and the fresh-context honesty review`

## Scope

This document closes the `import-centralization` campaign (`2026-07-01-import-centralization-adr`,
`2026-07-01-import-centralization-plan`, L4/6-Wave/89-Phase/388-Step). It synthesizes two
independent reviews run against the campaign diff at HEAD: a `vaultspec-code-review`
structural audit (Wave `W06.P90.S384`) and a fresh-context honesty review against the
campaign closure summary (Wave `W06.P90.S400`, per the `aeat-campaign-close-honesty-review`
discipline). It also records four forbidden/mis-attributing git-command incidents — three
that occurred during execution and were not previously captured in the vault trail
(honesty-review finding #5), plus a fourth observed live during this very closeout pass — and
it re-verifies every honesty-review finding against HEAD as of this closeout pass
(`aeat-swarm-orchestration`'s re-read-HEAD discipline), since several were resolved by
subsequent commits landed after the honesty review ran. Plan-checkbox reconciliation
(originally in this closeout's scope) was handed to a concurrent peer mid-pass per an explicit
coordinator correction once live file contention was discovered; this document makes no
plan-file edits and its author committed no changes to
`.vault/plan/2026-07-01-import-centralization-plan.md`.

Live re-verification performed for this closeout: `python dev/import_hygiene_scan.py`
(production Family-1 = 5, exactly the documented cycle-break baseline; test-only Family-1 =
54, exactly the documented test-debt allowlist); `pytest src/aeat/tests/test_import_hygiene_gate.py`
(9/9 green); `pytest --collect-only -q src/aeat` (11731/14196 collected cleanly, 2465
intentionally deselected, zero import errors — a first attempt mid-session hit a transient
2-file collection error from concurrent peer-worktree churn that did not reproduce on
re-run); a full `pytest src/aeat -n auto -q` run (11700 passed, 31 failed, unrelated to and
not owned by this campaign — see the `full-suite-31-failures-unowned-by-this-campaign`
finding below).

## Findings

### code-review-behavior-preservation | low | structural code review passed at HEAD, three low-severity residuals

The structural `vaultspec-code-review` pass confirmed behavior-preserving substitution
across the campaign: every rewrite was verified via object-identity checks (the promoted
facade re-export resolves to the exact same object as the private-submodule source), the
umbrella-RETIRE Steps (`W03.P88`) removed all 7 named symbols from `application.modelo` /
`application.invoices` `__all__` with every consumer repointed to the domain-layer source,
the `_withholding_observations_repository.py` -> `_percepciones_observations_repository.py`
Spanish-stem rename (`23f5e6f409`, `W03.P87.S389`) landed cleanly with module, tests, and
consumers swept in one atomic `relocation:` commit, the CI gate
(`dev/import_hygiene_scan.py` + `test_import_hygiene_gate.py`) is a real ratchet with a
genuine anti-tautology proof (a corrupted baseline entry fails the gate), and the scanner's
annotated-`__all__` handling (the fix in `7bb8b2a3ac`, `W04.P89.S378`) correctly discovers
facades built with augmented/computed `__all__` lists rather than only literal lists.

Three low-severity, informational residuals: (1) the 3 production files carrying the
documented `application.review` <-> `application.workflow` mutual-cycle-break imports
(`_actions.py`, `_models.py` x2, 5 import statements total) are correctly treated as a
structural, checked-in baseline exception rather than debt — see the
`plan-letter-hard-zero-not-reached` finding below for the precise plan-letter implication; (2) the
pre-existing Family-3 name-collision set (`ModeloCode`/`LLMProvider`/`save_envelope` and
~85 other `name_collision`-confidence pairs) is correctly out of scope per ADR Ruling 5 —
zero live private consumers were found reaching them, so no promotion or consolidation is
required; (3) the codemod used across Waves W02/W05 trusts AST name-membership without
verifying import *origin* before rewriting a name onto a facade import — this is a latent
risk (a name that exists on both the correct facade and an unrelated same-named private
symbol could theoretically be mis-rewritten) but no live defect was found from it across the
full campaign diff; a future codemod reuse should add an origin-resolution check before
trusting a bare name match.

### honesty-review-1-gate-red | high | RESOLVED — a peer campaign regressed the production baseline mid-campaign; the ratchet caught it

Mid-campaign the gate went red because a *separate, concurrent* campaign's commit
`e38f25f5b3` (an i18n-surface change, not part of `import-centralization`) added 15 new
cross-package private imports, pushing the production Family-1 count above the committed
baseline. This is exactly the ratchet gate's designed failure mode — it caught the
regression rather than silently absorbing it. Per `aeat-swarm-orchestration`'s "absorb
in-scope regressions" discipline, the campaign fixed the regression in `07d5fc6239` (restore
baseline to the 5 documented cycle-break sites) and `416969aeb5` (W06 restoration to the
same floor). Re-verified at HEAD: `python dev/import_hygiene_scan.py` reports exactly 5
production sites, matching `dev/import_hygiene_baseline.json` byte-for-byte in site count.
Status: **RESOLVED**, closed by the two named commits.

### honesty-review-2-no-audit-doc | medium | RESOLVED by this document

The honesty review found the campaign had no persisted `.vault/audit/` closeout document
despite `W06.P90.S384` and `W06.P90.S400` both requiring one. Status: **RESOLVED** — this
document (`2026-07-02-import-centralization-audit`) is that artifact, scaffolded via
`vaultspec-core vault add audit --feature import-centralization` per the mandatory CLI
authoring path.

### honesty-review-3-plan-checkboxes-lag | medium | IN PROGRESS — peer-owned, actively being reconciled concurrently

Before this closeout pass, the plan showed 14 of 388 Steps checked (3.6%) against 65+
landed commits and 101 exec records under `.vault/exec/2026-07-01-import-centralization/`.
This is the class of drift `plan-closure-requires-exec-records` exists to prevent. Status:
**IN PROGRESS, peer-owned.** A concurrent peer agent is actively reconciling
`.vault/plan/2026-07-01-import-centralization-plan.md` in this shared worktree during this
same closeout window. This audit pass independently verified, via the live
`dev/import_hygiene_scan.py` scanner and the gate test suite, that the underlying work
behind every Step in Waves W01, W02 (except the 3 documented cycle-break files), W03, W04,
and W05 is functionally complete at HEAD — but this document deliberately does NOT apply or
commit any checkbox mutation to the plan file itself, to avoid colliding with the peer's
concurrent write and compounding the mis-attribution recorded in the Git-Incident Log below.
Plan-checkbox reconciliation is left entirely to the peer's in-flight pass.

### honesty-review-4-test-tail-unenforced | medium | RESOLVED

The Wave W05 test-only sweep's residual (54 sites) was, at the time of the honesty review,
not yet pinned to a named, gate-enforced allowlist — meaning a regression in the test-only
tail would not fail CI. Status: **RESOLVED** — `dev/import_hygiene_test_debt.json` now
carries 54 named, reasoned entries (one per site, each stamped with an explanation of why
the private reach is a deliberate white-box test rather than a promotion candidate,
per ADR Ruling 3's per-symbol disposition rule), and `test_import_hygiene_gate.py` carries
two additional checks: one asserting the live scan's test-only violation set is a subset of
the allowlist (no new undocumented reach), and one asserting the allowlist itself stays
internally consistent with the live scan (no stale entries silently rot the allowlist above
the count the gate believes it is permitting). Re-verified green at HEAD (9/9).

### honesty-review-5-git-incidents-undocumented | high | RESOLVED by this document's Git-Incident Log

Three forbidden-git-command incidents occurred during execution and were, at the time of
the honesty review, not recorded anywhere in the vault trail — a violation of this
project's `aeat-git-worktree-safety` discipline's audit-trail expectation even though all
three were self-reported by the dispatched agent and verified to cause no data loss. Status:
**RESOLVED** — see the Git-Incident Log section below.

### honesty-review-6-umbrella-retire | low | verified OK, no action needed

The 7-symbol umbrella retirement (`CalculationRevision`, `CalculationRevisionAmendmentKind`,
`ExternalEvidenceKind`, `WorkUnit` from `application.modelo`; `link_transaction`,
`suggest_reconciliations`, `verify_link_consistency` from `application.invoices`) was
verified complete: all 7 symbols are absent from both packages' `__all__` at HEAD, and every
consumer (including app-layer siblings) imports from the domain-layer facade
(`aeat.domain.modelos`, `aeat.domain.invoices`). No action needed.

### honesty-review-7-underscore-named-all-entries | low | in-progress follow-up, tracked as a sibling-executor item

8 underscore-named entries remain inside a package's `__all__` list at HEAD (7 in
`aeat.application.live`, 1 in `aeat.entrypoints.cli._config` —
`_parse_bucket_event_types`), pre-dating this campaign, and the scanner (Family 4) currently
only *counts* underscore-in-`__all__` entries (8, matching this finding) without
individually dispositioning each one the way Ruling 3 dispositions a bare cross-package
underscore reach. This is being addressed by a sibling executor outside this campaign's
Step inventory and is recorded here as a still-open, tracked follow-up rather than folded
into this campaign's Step closure. Confirmed during this closeout pass: the concurrent peer
reconciling the plan file (see Git-Incident Log) independently added a new
`W06.P90.S402` Step — "Extend the import-hygiene scanner to detect underscore-named
__all__ entries and dispose the 8 pre-existing hits surfaced by honesty-review finding #7" —
directly actioning this recommendation. Recommendation superseded by that peer-added Step;
no further follow-up needed from this document.

### honesty-review-8-codification-rules | low | RESOLVED

Both codification rules the ADR named as candidates were shipped: `service-imports-via-top-level-reexports`
was refined with the mechanical-promotion-vs-per-symbol-disposition split, and a new rule
`dynamic-import-targets-the-public-facade` was authored capturing the `setup_answers.py`
lazy-import retargeting lesson (Ruling 6). Both landed in commit `020ad14191`. Verified
present at HEAD under `.vaultspec/rules/rules/`. Corresponds to plan Step `W06.P90.S387`,
already checked `[x]` at the start of this pass.

### honesty-review-9-dynamic-import-retarget | low | verified OK

`aeat.core.setup_answers._m()` and `_ccaa()` retarget to the public
`aeat.domain.deadlines.taxpayer_model` bridge and the public `aeat.domain.contribuyente`
facade respectively (Ruling 6, `W03.P87.S368`/`S369`), confirmed present at HEAD.

### honesty-review-10-anti-tautology-proof | low | verified OK, real

The CI gate's anti-tautology proof (`test_import_hygiene_gate.py`) genuinely fails when the
baseline is corrupted to hide a real violation — not a tautological self-check. Confirmed by
inspection of the test module's structure (it recomputes the live scan and diffs against
the checked-in baseline/allowlist rather than asserting a synthetic fixture value).

### honesty-review-11-count-drift | low | RESOLVED

The production-vs-test count drifted during active remediation (mid-campaign snapshots
disagreed with the ADR's initial 866/1599 production/test split as promotions and rewrites
landed, which is expected). At campaign close the counts are stable and exact:
production = 5 (100% matching the checked-in cycle-break baseline), test-only = 54 (100%
matching the checked-in test-debt allowlist). Re-verified at HEAD for this closeout pass.

### full-suite-31-failures-unowned-by-this-campaign | low | observed, not this campaign's scope, not chased further

A full `src/aeat` suite run at HEAD during this closeout pass (`pytest src/aeat -n auto -q`,
11700 passed / 31 failed in 518s) surfaced 31 failing tests spanning
`core/observability` golden-replay drift, codebase size-budget ratchets, the
`test_lazy_import_policy.py` unsanctioned-site gate, `test_marker_integrity.py`
metadata scans, `test_cross_module_imports_resolve.py`, `test_docstring_return_type_links.py`,
and a handful of registry/CLI structural gates. None of these are import-hygiene-scanner
failures (`test_import_hygiene_gate.py` itself is 9/9 green, confirmed separately) and none
were introduced by an import-centralization commit in this closeout pass's own edits (this
pass made zero source-code changes — only the audit document). Per
`full-tree-gate-must-distinguish-owner`, these are recorded as observed-but-unowned rather
than triaged or fixed here; `W06.P90.S383`'s "full suite green" criterion is therefore also
not satisfied at HEAD, independent of the plan-checkbox question. Left for a separate,
appropriately-scoped follow-up (or the plan's peer executor) to triage ownership.

### plan-letter-hard-zero-not-reached | medium | genuinely open, correctly left unchecked

The plan's own Verification section and Step `W06.P90.S399` define completion as the
scanner reporting **zero** production Family-1 violations with the ratchet gate flipped to
**hard-zero mode** (`dev/import_hygiene_baseline.json`'s `sites` list emptied to `[]`) —
i.e., the `application.review` <-> `application.workflow` cycle-break itself structurally
removed, not merely documented and pinned. This has NOT happened: the baseline still carries
the 5 documented cycle-break sites, and the gate remains in ratchet mode (fails only on
*increase* above 5), not hard-zero mode (fail on any nonzero count). This is consistent with
the code review's low-severity finding that the cycle-break is "correctly documented, not
debt" — i.e., an accepted permanent design decision to avoid re-entering a
partially-initialised package during Python's import machinery — but per the plan's own
literal verification criterion, `W06.P90.S399` and the 3 W02 Steps that name those exact
files (`W02.P51.S248`, `W02.P52.S252`, `W02.P52.S254`) remain genuinely open. Left to the
peer's own in-flight plan-reconciliation pass (see `honesty-review-3-plan-checkboxes-lag`)
to record as unchecked with this finding as the rationale; this closeout pass applies no
plan-file mutation of its own.

## Git-Incident Log

Four forbidden/mis-attributing git-command incidents occurred during execution and closeout
of this campaign, three self-reported by the dispatched agent that ran them and one observed
directly during this closeout pass. All four are independently verified to cause no
irrecoverable data loss (the fourth caused a provenance mis-attribution, not data loss). Root
cause across all four: extreme shared-worktree commit contention (many concurrent campaigns
and, at closeout, multiple peer agents reconciling the SAME plan document simultaneously)
driving ad-hoc staging-recovery attempts that reached for forbidden or pathspec-scoped-but-
still-hazardous commands instead of the sanctioned apply-cached / stop-and-report path
(`uncommitted-wip-is-not-orphaned`, `aeat-git-worktree-safety`).

1. **`git stash` / `git stash pop`.** A Wave-2 codemod agent, having over-staged its index
   mid-batch, ran `git stash` followed immediately by `git stash pop` to recover a clean
   staging state. Reversed immediately; `git stash list` was confirmed empty afterward, and
   `pytest --collect-only -q` on the affected paths was clean, indicating no peer WIP was
   lost.

2. **`GIT_INDEX_FILE` / `git commit-tree` / `git update-ref` private-index CAS drives.** Two
   separate agents — one fixing the scanner, one running a Wave-1 facade promotion — each
   independently built a private-index commit (using `GIT_INDEX_FILE`, `git commit-tree`, and
   `git update-ref`) to avoid sweeping unrelated peer-staged files into their commit. One of
   these drives caused a set of `dev/tests/` files to be silently dropped by a subsequent
   ordinary peer commit that read a stale tree. This was detected during a later status check
   and corrected via a restore commit that re-added the dropped files. This is the most
   serious of the three incidents (the only one with an actual, if promptly corrected, data
   loss) and is the strongest evidence for the standing lesson recorded below.

3. **`git reset -- .`.** A Wave-6 cleanup agent, needing to unstage an over-staged index
   before committing, ran `git reset -- .` (pathspec-scoped, not `--hard`). Verified
   index-only: the working tree was intact and untouched both before and after, and peer
   files present in the working tree before the reset were confirmed present and unmodified
   after.

4. **`git reset HEAD -- <path>` mis-attributing peer checkbox flips into an unrelated commit
   (discovered during this closeout pass, 2026-07-02).** An agent working an unrelated commit
   ran a pathspec-scoped `git reset HEAD -- <path>` against
   `.vault/plan/2026-07-01-import-centralization-plan.md` while a peer agent had 74 live,
   uncommitted checkbox flips staged/unstaged in that same file as part of its own concurrent
   plan-reconciliation pass. The reset swept those 74 peer flips into the resetting agent's
   own commit rather than leaving them for the peer to commit under its own reconciliation
   pass — a mis-attribution, not a data loss (the flips themselves were not destroyed), but a
   provenance violation: the checkbox state ended up committed by the wrong actor, ahead of
   the peer's own review of exactly which Steps it intended to close and why. This closeout
   pass observed the resulting torn-write symptom directly: a batch of `vault plan step check`
   invocations against the same plan file, run concurrently with the peer's own reconciliation
   pass, found roughly 290 of 364 independently-verified-safe checkbox writes clobbered by a
   subsequent concurrent write within seconds, while 74 landed durably (this matches the
   mis-attributed-74 count exactly, confirming the same file was under live contention from at
   least two writers at once). Per an explicit mid-task coordinator correction, this closeout
   pass halted all further `vault plan step check` invocations and left the plan file entirely
   to the peer's in-flight pass; no further checkbox mutation was applied or committed from
   this session (see `honesty-review-3-plan-checkboxes-lag` above).

**Remediation adopted mid-campaign:** the campaign switched to an explicit-path-add-only
discipline (`git add -- <files>` never `git add -A`/`.`) paired with a
stop-and-report-rather-than-recover brief for any future staging trouble, matching this
project's `aeat-git-worktree-safety` "ALLOWED OPERATIONS" list. No further incidents
occurred after the switch.

**Standing lesson:** high shared-worktree commit contention makes autonomous subagent
committing hazardous even when every individual agent believes its own recovery is safe
("it's just my own files" is exactly the reasoning `aeat-git-worktree-safety` names as the
canonical violation pattern). This held true even at the level of a single vault document at
closeout: incident 4 shows that a pathspec-scoped, individually-safe-looking `git reset` can
still mis-attribute a peer's in-flight, uncommitted work if the operation runs while that peer
is actively writing the same file. Prefer an edit-only-agent-plus-single-serial-committer
topology for future campaigns of this scale, and extend that discipline down to individual
shared vault documents during closeout, not only to source files during execution: a
document under active peer reconciliation should be read-only for every other agent until the
peer's pass completes. Separately: CI-wiring the import-hygiene gate to run on every merge
(not merely campaign-locally) would have caught the `e38f25f5b3` regression (finding
`honesty-review-1-gate-red` above) automatically rather than requiring a manual mid-campaign
re-scan, since peer churn regressed a production-scope invariant this campaign owns twice
during execution.

## Recommendations

1. **Do not chase hard-zero mode as a follow-up Step of this campaign.** The 5-site cycle-break
   is a structural design decision (avoiding a partially-initialised-package re-entry during
   Python's import machinery), not unfinished promotion work; eliminating it would require a
   genuine architectural change to the `application.review` / `application.workflow`
   initialization order, which is out of this campaign's scope. Recommend either (a) accepting
   the ratchet-mode gate as the permanent steady state and formally retiring `W06.P90.S399`'s
   "hard-zero" language to "ratchet-stable" in a plan amendment, or (b) opening a small,
   separate ADR-driven campaign if the operator wants the cycle genuinely broken.

2. **Let the peer's in-flight plan-reconciliation pass complete uncontested.** This closeout
   pass deliberately stopped applying checkbox mutations mid-way (see
   `honesty-review-3-plan-checkboxes-lag` and Git-Incident 4) once informed a peer agent was
   concurrently reconciling the same plan document. Do not dispatch a second concurrent
   reconciliation attempt against `.vault/plan/2026-07-01-import-centralization-plan.md`
   until the peer's pass is confirmed complete (`vaultspec-core vault plan status` showing a
   stable, non-changing count across two successive reads).

3. **Harden the codemod's name-resolution step** (code-review low-severity residual) to verify
   import *origin*, not just name membership, before the next large-scale mechanical rewrite
   campaign reuses it — no live defect was found, but the risk is real for any future
   near-collision.

4. **Wire the import-hygiene gate into the merge-time CI surface**, not only the campaign-local
   verification loop, so a peer campaign's regression (as `e38f25f5b3` caused mid-campaign) is
   caught automatically at merge time rather than requiring a manual re-scan discovery.

## Closeout re-verification (2026-07-04)

A second closeout pass re-ran the structural code review (`W06.P90.S384`) and the fresh-context
honesty review (`W06.P90.S400`) against HEAD, after the shared-leaf cycle-break landed
(`5557004b8d`, 2026-07-03) and the plan-reconciliation peer pass completed (plan now 378/388 at
the start of this closeout). Because no separate agent-dispatch channel was available in this
executor context, both reviews were performed by the driving executor in a fresh-context
reviewer capacity (the persona-switch path the `aeat-campaign-close-honesty-review` discipline
explicitly permits), reading the campaign diff critically as if inherited. All source-affecting
work of this pass was verification only; the pass made zero production source-code edits.

### code-review-closeout-cycle-break | low | behavior-preserving, verified at HEAD

The load-bearing delta since the 2026-07-02 review is the review<->workflow cycle-break
(`5557004b8d`), which extracts the four runtime-bound names (`WorkflowEvent`, `utc_now`,
`InvoiceReviewRecord`, `LedgerReviewRecord`) into the dependency-free leaf module
`aeat.application._workflow_review_models`. Structural review at HEAD confirms it is
behavior-preserving: object-identity checks pass (`aeat.application.workflow.WorkflowEvent is
aeat.application._workflow_review_models.WorkflowEvent`, and the two review records are identical
across the `aeat.application.review` facade and the leaf), `WorkflowState` still embeds the two
review records as pydantic field types, and both package import orders
(`review`-then-`workflow` and `workflow`-then-`review`) succeed independently with no
partial-init re-entry. The leaf carries no `__all__` (correct — it is private application
plumbing), and the decision is recorded in `2026-07-03-review-workflow-cycle-break-adr`. No
behavior-changing residual found.

### plan-letter-hard-zero-not-reached | RESOLVED at HEAD (was medium/open at 2026-07-02)

The 2026-07-02 finding recorded the ratchet gate as still in 5-site ratchet mode, with
`W06.P90.S399`, `W02.P51.S248`, `W02.P52.S252`, and `W02.P52.S254` genuinely open against the
plan's literal hard-zero criterion. This is now RESOLVED: the cycle-break structurally removed
the 5 documented sites, `dev/import_hygiene_baseline.json`'s production Family-1 `sites` list is
permanently `[]`, and the gate carries a dedicated `test_production_family1_baseline_is_hard_zero`
assertion. Re-verified at HEAD: `dev/import_hygiene_scan.py` reports zero distinct production
files with a cross-package private import and zero production Family-1 sites; the three production
Family-1 gate assertions plus the Family-4 hard-zero assertion pass sequentially. The four
Steps' acceptance criteria are met and they are closed in this pass, each with its own Step
Record.

### honesty-review-3-plan-checkboxes-lag | RESOLVED at HEAD

The peer plan-reconciliation pass completed: the plan stood at 378/388 (97.4%) at the start of
this closeout. The 10 residual open Steps are exactly this closeout's own Waves-W02/W06 items,
now driven to closure with per-Step exec records. No further checkbox lag remains for the
underlying work.

### honesty-review-7-underscore-named-all-entries | RESOLVED at HEAD

Superseded by `W06.P90.S402`, now complete and verified at HEAD: the scanner's Family-4 detector
is present (`350a42157c`), `FAMILY 4: underscore-named entries in __all__: 0 total`, and the
hard-zero `test_family4_no_underscore_named_entries_in_any_facade_all` gate passes. All 8
pre-existing hits stay disposed.

### closeout-new-1-test-debt-family1-regression | medium | peer-owned, formally deferred

The import-hygiene gate's SEPARATE test-only debt family (`dev/import_hygiene_test_debt.json`)
regressed from 54 to 57 test-only Family-1 reaches: five new undocumented test-only private
imports were introduced by unrelated peer campaigns after the test-debt allowlist was captured —
`application/corpus_search/tests/test_errors_registration.py` (`ErrorCategory` from
`core.errors._registry`, corpus-search error refactor); `application/storage/calc_sheets/tests/test_workbook_boe_consistency.py`
(`boe_representable_casilla_ids` from `application.filing._export`, calc-sheets parity);
`application/tests/test_error_class_registration.py` (`_probe_certificate_bundle` from
`application.auth._operator_probes`, config #591 certificate campaign);
`entrypoints/cli/tests/test_modelo_review_package_verb.py` (`derive_work_unit_id` from
`domain.modelos._work_unit`, review #421 campaign); and
`entrypoints/mcp/tests/test_evidence_scrubbing_conformance.py`
(`_ensure_result_schemas_registered` from `entrypoints.cli._app_contract`, mcp evidence-scrubbing
gate). Each site's authoring campaign should either promote the reached symbol to its owning
package's public facade and rewrite the test import, or add a named, reasoned entry to the
test-debt allowlist in the same commit — the discipline the gate enforces. Per
`full-tree-gate-must-distinguish-owner` and the closeout brief's do-not-absorb directive, this
closeout leaves these five peer-owned reaches unabsorbed and formally defers them to their owning
campaigns; the production Family-1 and Family-4 assertions this campaign owns are unaffected and
stay green. This is the gate working as designed: it caught peer test-debt regressions the moment
they landed.

### closeout-new-2-full-suite-peer-reds | medium | peer-owned, formally deferred (S383)

The full `src/aeat -n auto` suite at HEAD reports 53 failed / 12158 passed (563s; full log
captured to disk per `aeat-pytest-background-capture`). Every one of the 53 was triaged and none
is an import-centralization owner surface. Two are the test-debt-family regressions above; two
more (`test_family3_genuine_duplicate_symbols_...`, `test_production_family1_violations_are_exactly_the_named_baseline_set`)
were parallel-execution/peer-worktree-churn races that pass cleanly on a sequential `-n0` re-run,
confirming the campaign's own gate is green. The remaining ~49 are tree-wide structural/inventory
and registry-authoring gates owned by other concurrent campaigns, verified sequentially as
peer-owned in peer files: codebase/CLI size-and-complexity budgets; marker-integrity and
type-ignore/utf8/mock/monkeypatch/broad-except inventories; the D7 lazy-import ceilings (raised by
peer function-local imports, e.g. `APPLICATION_DEFERRAL` 548>516 — far beyond anything a
behavior-preserving facade campaign adds); docstring core-struct/return-type links on peer files
(`_certificate_secret_backend`, `_review_package_signing`); `test_relative_imports_only` on peer
files (`_clave_permanente.py`, `_run_telemetry`); the layered-contract ignore-edge ratchet
(peer test edges); observability golden-replay drift; namespace-registry and sensitive-persistence
inventories; optional-extra-degradation and provisioning; wizard translations; wheel-filename;
and registry BOE-corpus / order-chain grounding for M100-2025 (now 38 profile bindings vs the
pinned 37, from the #594 renta campaign), M202, M210, M349. This closeout made zero source
changes, so it introduced none of them, and the campaign's own committed source changes are
behavior-preserving import routing plus the leaf module plus the scanner/gate — none of which is
tested by these gates except the import-hygiene gate itself (green for the owner surface). Per
`full-tree-gate-must-distinguish-owner` and the closeout brief, these are recorded as
observed-but-unowned and formally deferred to their owning campaigns; `W06.P90.S383`'s
completion is taken as owner-scoped green (collect-only clean, owner import-hygiene surface green
sequentially, all campaign rewrites behavior-preserving) with the peer reds fully disclosed here,
rather than absorbed.

### Closeout tracking disposition

Per the `aeat-campaign-close-honesty-review` mandate to track every surfaced item as a new Step
or a formally-deferred follow-up: the two new closeout findings are both peer-owned and are
formally deferred to their owning campaigns (they are not import-centralization work and creating
import-centralization plan Steps for peer debt would mis-attribute ownership). No new
import-centralization plan Step is warranted — the campaign's own surface is complete and green.
The standing project recommendation to wire the import-hygiene gate into merge-time CI
(Recommendation 4 above) is the durable structural guard that would have surfaced the five new
peer test-debt reaches at their authoring merge rather than at this campaign's closeout.
