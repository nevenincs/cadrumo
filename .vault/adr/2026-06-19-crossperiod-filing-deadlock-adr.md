---
tags:
  - '#adr'
  - '#crossperiod-filing-deadlock'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - '[[2026-06-19-crossperiod-filing-deadlock-research]]'
---
# `crossperiod-filing-deadlock` adr: `Cross-period filing deadlock: late local work file and local-chain export` | (**status:** `accepted` — Decision A implemented; Decision B implemented in a refined same-year scope)

## Problem Statement

The filing-persona campaign surfaced finding C0 — a cross-period observation deadlock that unifies three separately-reported defects (M130 quarter-to-quarter pago-fraccionado carry, M303 1T to 2T IVA compensacion carry, M100 M130-fold-in). The engine arithmetic for every cross-period aggregation is correct, yet the aggregation is operationally UNREACHABLE for any late filing or prior-year reconstruction: a taxpayer can export only the first period of a chain. Proof from the testimonials: the M130 reconstruction produced 1 of 5 `.boe` files (only 1T); the M303 reconstruction produced 1 of 2, and the 420-euro 1T credit never reached the 2T casilla 110 (2T stayed 945 instead of the expected 525).

The deadlock is a closed loop across two gates.

**Gate A — the `work file` obligation-window gate.** `work file` (`WorkflowPurpose.FILE`, the LOCAL mark-as-filed verb that does not contact AEAT) computes its obligation schedule through `compute_obligation_schedule`, which derives the fiscal year from `today.year` (`src/aeat/domain/deadlines/_engine.py`: `engine.compute(profile, today.year, today=today)`). For any past-year period the obligation is therefore never present in the computed schedule at all, so the per-target filter in `_stage_computing_deadlines` (`src/aeat/application/workflow/_engine.py`) finds `obligation is None` and aborts `NO_PENDING_OBLIGATION`. `work file` is the ONLY producer of the local filed observation (`persist_filed_revision_observation`, `src/aeat/application/modelo/_filed_revision_observation.py`, co-emitted with `MODELO_FILED` by `persist_filed_revision`) that the next period's `previous_filing` carry binding reads. With `work file` refused, the carry observation is never written, so the next quarter's `calculate` has nothing to read.

**Gate B — the cross-period clean-state gate.** Even when the prior observation IS written, the dependent period's `verify` (and `file`) runs `evaluate_cross_period_clean_state` (`src/aeat/application/calculations/_cross_period_clean_state.py`) and emits a BLOCKING `CROSS_PERIOD_DEPENDENCY_UNCLEAN` finding because the prior period's local `app_filing` record carries no official AEAT evidence (`MISSING_AEAT_ACCEPTANCE`, `MISSING_EXTERNAL_EVIDENCE`, `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`). Export requires a verify-granted revision, so the dependent period can be neither verified nor exported. The only remediation the gate offers is to import an official AEAT justificante — which a never-filed historical chain cannot produce, and which live filing is prohibited from generating.

The carry value and the official-evidence requirement are separable: the `previous_filing` resolver reads the observation store directly (`repository.load_observation(...)` in `src/aeat/application/calculations/_binding_prefill.py`), never the clean-state verdict. Today both gates conspire so that neither the value nor the export is reachable for a late filer.

## Considerations

The decision must respect five standing rules without weakening any of them:

- `aeat-safety-legal-gates`: never perform live AEAT submission. Build, validate, verify, export, and require human filing outside the app. Export is explicitly a non-filing operation (the local finish line) and `work file` is a LOCAL mark-as-filed, not an AEAT contact.
- `local-filed-observations-are-non-official-evidence`: locally-filed observations carry the non-official `app_filing` source kind and must never be added to `_OFFICIAL_SOURCE_KINDS` or laundered past the gate that protects an official dependent filing.
- `carried-observations-stamp-their-revision` and `revision-resolution-is-law-determined`: a carried value must re-confirm its registry revision; a divergent stamp blocks, an absent stamp advises.
- `no-silent-under-declaration`: an unrouted or non-official basis must surface, never vanish into a silent grant.

The two distinct operator intents the system must serve are single-period export (already works: calculate, verify, export — `work file` is not required to reach a `.boe`) and cross-period chain reconstruction / late filing (broken: the taxpayer reconstructs a closed-window year locally, must produce a `.boe` for every period, and will file all of them at AEAT externally; no official justificante exists yet for any period in the chain).

The deadline engine already classifies a past window as OVERDUE and already builds a registry-grounded `Recovery` (recargo / extemporaneo) payload for it (`_overdue_recovery_or_none`, `build_recovery_for_overdue`). The system already tells operators at M100 create time "plazo voluntario vencido, presenta con recargo" — late filing is acknowledged elsewhere; only `work file` refuses it.

## Constraints

- **Single-producer property of the obligation schedule.** The `NO_PENDING_OBLIGATION` gate and the operator state read-projection (`pending_obligations`) both route through `compute_obligation_schedule` so they cannot draw a divergent obligation set. Any fix to the FILE-target year scoping MUST preserve that single-producer invariant: the projection's as-of-today view stays year-of-today; only the explicit-target FILE gate resolves the target period's own filing year.
- **One canonical carry mechanism.** `calculation-source-canonical-mechanism` and `one-aggregation-path-pull-equals-calculate` forbid modelling one cross-period fold-in two ways. The carry must keep reading the single `previous_filing` observation; this ADR does not add a parallel read-a-verified-revision carry source.
- **The official-evidence gate still binds the future, prohibited remote-submission path.** Downgrading the official-evidence blockers on the LOCAL export path must not delete them: they remain BLOCKING for any path that asserts AEAT acceptance (`aeat_accepted`, justificante reconcile, a future live-submission ADR).
- **M303 has independent preconditions.** The M303 end-to-end chain is also gated by C1 (casilla 65 `jurisdiction_scope` defaulting to 0) and C2 (`iva.prorrata-porcentaje` formula-divergence on the 0/0 ordinary case). Those are separate findings with separate remediation; the M303 e2e test in this feature must apply their documented workarounds (or land after their fixes).

## Implementation

The fix is two coordinated changes, one per gate, plus their tests. It keeps the single canonical carry mechanism and adds no parallel write path.

### Decision A — recognise a historical obligation and allow late local `work file`

In the FILE workflow's deadline stage (`_stage_computing_deadlines`, `src/aeat/application/workflow/_engine.py`), when an explicit `(target_modelo, target_period)` is present, resolve the obligation schedule for the target period's filing year rather than `today.year`. This is the precise correction of the `compute_obligation_schedule` year-derivation bug: a 2024 1T obligation is then found in the 2024 schedule, classified OVERDUE, and carries its registry-grounded `Recovery` payload.

With the historical obligation now visible, split the two abort reasons by their true meaning:

- `NO_PENDING_OBLIGATION` — the obligation is absent from the target-year schedule (the modelo / period never applied to this profile, or was scoped out pre-activity). Still refuse: no obligation ever existed.
- `DEADLINE_PASSED` — the obligation existed and is overdue. For `WorkflowPurpose.FILE`, no longer a hard abort: record the obligation as overdue, carry its `Recovery` (extemporaneo / recargo) marker onto the workflow step `details`, and proceed to persist the local filed observation. The persisted `app_filing` observation then seeds the next period's carry.

The projection's as-of-today schedule is untouched; the single-producer property holds because only the explicit-target FILE branch re-scopes to the target year, and it resolves the same engine over the same profile.

### Decision B — admit a complete LOCAL chain to verify / export with a non-official advisory

Introduce an explicit evidence tier in the cross-period clean-state evaluation (`src/aeat/application/calculations/_cross_period_clean_state.py`), mirroring the existing `no_prior_obligation` facet pattern. A dependency is locally clean when, and only when:

- its observation is present and is a genuine `app_filing` local chain (source kind `app_filing`, not `operator_manual`, not a botched official-evidence import);
- the required source casillas are present and their values match the prior period's VIGENTE local revision (`OBSERVATION_REVISION_VALUE_DIVERGENCE` does not fire);
- the revision stamp re-confirms against the law-determined revision (`REGISTRY_REVISION_DIVERGENCE` does not fire); and
- the ONLY remaining blockers are the official-evidence delta: `MISSING_AEAT_ACCEPTANCE`, `MISSING_EXTERNAL_EVIDENCE`, `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`.

A locally-clean dependency carries a typed marker (e.g. a `non_official_local_chain` facet on `CrossPeriodDependencyEvidence`). In `_cross_period_clean_state_findings` / `_require_cross_period_clean_state` (`src/aeat/application/modelo/_verification_actions.py`), a locally-clean dependency emits a NON-BLOCKING ADVISORY (WARNING severity) — "this filing rests on a non-official local-only chain; file all periods at AEAT and reconcile the official justificantes" — instead of the BLOCKING `CROSS_PERIOD_DEPENDENCY_UNCLEAN`. Every genuinely-unclean dependency (missing observation, missing filing record, value divergence, revision divergence, operator-manual source, group-member gaps, mismatched official evidence) stays BLOCKING exactly as today.

The official-evidence blockers are retained, not deleted: they continue to block any path that asserts AEAT acceptance. Only the LOCAL verify / export path treats the complete local chain as sufficient-with-disclosure.

### Net flow after the fix

M130 reconstruction: 1T calculate, verify, `work file` (overdue, recargo marker) persists the `app_filing` observation. 2T `calculate` auto-carries casilla 05 from 1T's observation; 2T verify emits the non-official advisory (locally clean) and grants; 2T exports. Repeat 3T, 4T; M100 folds in the four engine-computed casilla-19 values. M303: 1T, then `work file`, then 2T `calculate` carries the 420 euro into casilla 110, 2T resultado 525, 2T verifies (advisory), exports.

## Rationale

The deadlock is two gates, so the fix is two gates; neither alone produces the end-to-end exports the campaign demands. Gate A alone unblocks the carry value but leaves the dependent verify blocked on official evidence (the testimonials confirm 2T verify still blocks even when the carry is supplied by hand). Gate B alone has nothing to be clean about because no observation is ever written.

Decision A is the minimal, well-grounded correction of a literal bug: the obligation schedule was computed for the wrong year, so a historical obligation was structurally invisible and every past period collapsed to `NO_PENDING_OBLIGATION`. Recognising the target year cleanly separates "no obligation ever existed" (still refuse) from "obligation existed, now overdue" (allow, mark extemporaneo); the recargo machinery the engine already builds is exactly the marker that authorises a late local filing.

Decision B keeps the single canonical carry mechanism (the `previous_filing` observation), rather than the alternative of teaching the carry to read a verified-but-unfiled revision, which would add a second carry source and risk `calculation-source-canonical-mechanism` / `no-dormant-source-resolvers` drift. It refines the clean-state gate at exactly one seam (the precise complete-local-chain-lacking-official-evidence case) and surfaces it as a visible advisory, satisfying `no-silent-under-declaration`.

## Safety analysis (does this weaken `aeat-safety-legal-gates`?)

No. The safety guarantee is preserved on three independent grounds:

- **`work file` and `export` are not AEAT submissions.** `aeat-safety-legal-gates` explicitly permits build / validate / verify / export and a local mark-as-filed; it prohibits only live submission. Allowing a late LOCAL `work file` for a window that genuinely closed contacts AEAT zero times and is consistent with the system already advising "presenta con recargo" elsewhere. The overdue obligation must genuinely exist (found in the target-year schedule); a target that never had an obligation is still refused.
- **No non-official evidence is laundered past an official gate.** The `app_filing` source kind stays non-official and stays out of `_OFFICIAL_SOURCE_KINDS` (`local-filed-observations-are-non-official-evidence` is honoured at the data level). The official-evidence blockers remain BLOCKING for any AEAT-acceptance assertion. Decision B only changes what the LOCAL verify / export path does with a complete local chain, and it discloses the non-official basis as a prominent advisory rather than granting silently.
- **No silent under-evidenced filing.** Because the human files every `.boe` externally and the app surfaces the non-official local-chain advisory on every dependent period, the operator is never misled into believing a dependent period is officially evidenced. This is the genuine protection the gate exists to provide, and it is preserved.

The one place this ADR amends an existing rule is the interpretation of `local-filed-observations-are-non-official-evidence`: app_filing may satisfy the LOCAL export gate (with disclosure) but still never satisfies an official / remote AEAT-acceptance assertion. That refinement is recorded below as a codification candidate so the rule's wording is updated in lock-step.

## Consequences

Gains: the cross-period chains that compute correctly today become reachable. Late filers and prior-year reconstructions can export every period of a M130, M303, and M100 chain, with the carry auto-resolving and the non-official basis disclosed. The recargo / extemporaneo marker becomes operator-visible at the local filing step.

Difficulties and pitfalls: Decision B adds a tier to a safety-adjacent gate, so the boundary between locally-clean (advisory) and genuinely-unclean (blocking) must be exhaustively pinned by tests — a regression that widened the locally-clean set to admit a value-divergent or operator-manual prior would be a real safety hole. The official-evidence blockers must remain reachable as BLOCKING on the acceptance path (assert this explicitly). The deadline-year re-scoping must not leak into the as-of-today projection. The M303 end-to-end is additionally gated by C1 / C2 and cannot pass until those are worked around or fixed.

Bounded vs. broad: this is a bounded change — two functions and their clean-state helper, plus tests. It does not require restructuring the workflow engine, the registry, or the carry resolver. The blast radius is:

- `src/aeat/application/workflow/_engine.py` (`_stage_computing_deadlines`, and the FILE-target year resolution feeding it).
- `src/aeat/domain/deadlines/_engine.py` (`compute_obligation_schedule` or a target-year-aware sibling, preserving the single-producer property for the projection).
- `src/aeat/application/calculations/_cross_period_clean_state.py` (the locally-clean evidence tier and facet).
- `src/aeat/application/modelo/_verification_actions.py` (`_cross_period_clean_state_findings`, `_require_cross_period_clean_state`: advisory vs. blocking routing).
- `src/aeat/application/workflow/_models.py` (a typed overdue / extemporaneo marker on the FILE result, if not already representable).
- CLI / locale surfaces for the extemporaneo `work file` message and the non-official-local-chain advisory (authored only through the locale CLI).

## Test plan

Real-behaviour, real-adapter, no mocks / skips / xfail; values derived from the testimonials' worked arithmetic (engine-computed, not hand-recomputed from the registry formula under test).

- **M130 1T to 4T full local chain (the flagship).** Extend the existing `src/aeat/application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py` — which today bypasses the deadlock by calling `persist_filed_revision_observation` directly — with a sibling that drives the REAL `file_modelo_revision` (`work file`) path under a 2026 clock against 2024 periods. Assert: (1) `work file` for each overdue quarter SUCCEEDS and records the extemporaneo / recargo marker; (2) each subsequent quarter's `calculate` auto-carries casilla 05 (0, 900, 1900, 2900) with no `--binding`; (3) each dependent quarter VERIFIES with a non-blocking non-official-local-chain advisory and EXPORTS a `.boe`; (4) M100 0604 folds in the four engine-computed casilla-19 values (900+1000+1000+1000). All four quarters plus the annual produce `.boe` (5 of 5, versus 1 of 5 today).
- **M303 1T to 2T compensacion carry.** Extend `src/aeat/application/modelo/tests/test_e2e_ledger_m303_quarters_to_m390_annual.py` with the real `work file` path: 1T (a compensar -420), then `work file`, then 2T `calculate` reads casilla 110 = 420, 2T resultado = 525 (not 945), 2T verifies with the advisory and exports. Apply the C1 jurisdiction_scope=100 and C2 prorrata-equal-volumes workarounds, or sequence after their fixes.
- **Refusal still fires for a never-existing obligation.** Assert `work file` for a `(modelo, period)` with no obligation in the target-year schedule still aborts `NO_PENDING_OBLIGATION`.
- **Gate-B boundary pins (safety).** Assert that a dependent period whose prior carries `OBSERVATION_REVISION_VALUE_DIVERGENCE`, `REGISTRY_REVISION_DIVERGENCE`, `OPERATOR_MANUAL_SOURCE`, `MISSING_OBSERVATION`, or `MISSING_CURRENT_FILING_RECORD` STILL BLOCKS (is not admitted as locally clean). Assert the official-evidence blockers remain BLOCKING on any path that asserts AEAT acceptance, and that `app_filing` is still absent from `_OFFICIAL_SOURCE_KINDS`.
- **Single-producer / projection invariant.** Assert the as-of-today `pending_obligations` projection is unchanged by the FILE-target year re-scoping.

## Codification candidates

- **Rule slug:** `late-local-work-file-allowed-for-existing-overdue-obligation`. **Rule:** A LOCAL `work file` (mark-as-filed, no AEAT contact) MUST be permitted for a closed / overdue window when the obligation genuinely existed for the target `(modelo, period, year)` — recording the registry-grounded extemporaneo / recargo marker — and MUST still refuse (`NO_PENDING_OBLIGATION`) a target for which no obligation ever existed; the obligation schedule for an explicit FILE target is resolved against the target period's filing year, never `today.year`.
- **Rule slug:** `local-filing-chain-exports-with-non-official-advisory`. **Rule:** A dependent period whose ONLY cross-period blockers are the official-evidence delta over a complete, value-consistent, revision-confirmed `app_filing` local chain MUST verify and export with a NON-BLOCKING non-official-local-chain advisory (never a silent grant); every other unclean blocker stays BLOCKING, and the official-evidence demand remains BLOCKING for any AEAT-acceptance assertion. This refines, and must be promoted in lock-step with, `local-filed-observations-are-non-official-evidence`.

## Existing-test reconciliation (grounded re-review)

A grounded re-review via `vaultspec-rag search ... --type code` surfaced an existing test surface that this ADR MUST reconcile, and that sharpens the safety argument:

- **`src/aeat/application/modelo/tests/test_local_cross_period_carry.py`** already proves the *carry value* works (`test_local_file_then_next_period_calculate_carries_previous_filing_value`) — but only because its fixtures file under a present-day clock (`_T2`/`_T3`/`_T4`) against same-year (2026) periods, so the window is open and Gate A never fires. This is precisely why the engine arithmetic passes in tests while the real CLI deadlocks for a 2024 period at the 2026 clock. The new flagship e2e (a 2024-period chain under a 2026 clock through the REAL `file_modelo_revision`) is the missing coverage and should reuse these `_file_revision` / `_seed_130` helpers with a past-period setup.

- **`test_locally_filed_upstream_does_not_satisfy_filing_clean_state` (line 215) deliberately encodes the behaviour Decision B changes.** It asserts (a) the 2T verdict carries `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`, and (b) `file_modelo_revision` for 2T RAISES `ModeloCrossPeriodCleanStateError`, with the docstring "filing a dependent period requires real external evidence… the single decision that keeps the carry from laundering an unevidenced chain past the filing gate." Decision B refines exactly this. The four-quarter M130 chain REQUIRES each dependent quarter to `work file` successfully (each seeds the next quarter's carry observation), so the file-refused assertion in (b) cannot stand unchanged.

**Reconciliation (must land in the same change as Decision B):**

- Assertion (a) — the verdict-level blocker — is PRESERVED. Decision B does not delete `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` from the verdict; it reclassifies a dependency whose ONLY blockers are the official-evidence delta as locally-clean at the FINDING/policy layer. `verdict.blockers` may still contain the blocker.
- Assertion (b) — the file refusal — is UPDATED to the new policy: `file_modelo_revision` for a complete, value-consistent, revision-confirmed `app_filing` local chain SUCCEEDS and records the non-official-local-chain advisory; a record asserting `aeat_accepted = True` without official evidence STILL refuses. (`file_modelo_revision` sets `aeat_accepted = False`; there is no remote-acceptance path today, so nothing is laundered past an official gate.)
- `test_app_filing_source_kind_is_not_official_evidence` is PRESERVED verbatim — `app_filing` stays out of `_OFFICIAL_SOURCE_KINDS` at the data level.

**Sharpened safety argument.** The original D1 author treated "app_filing must not let a dependent period file" as the anti-laundering guarantee. The honest refinement: the chain Decision B admits is not *unevidenced* — it is *locally evidenced* (every period calculated, verified, and locally filed, values internally consistent and revision-confirmed); it lacks only OFFICIAL AEAT acceptance, which an app that prohibits live filing cannot produce. The "laundering" the rule feared is laundering past a REMOTE/OFFICIAL submission, which does not exist here. The only consumer is EXPORT — a `.boe` the human reviews and files externally — and the non-official basis is disclosed on every dependent period. The guarantee is preserved by retaining the blocker for any `aeat_accepted` assertion and by surfacing the advisory, not by refusing the local export.

## Grounded fix-site inventory

Pinned via `uv run --no-sync vaultspec-rag search … --type code`, verified at HEAD `7208bb3f0`:

- Gate A year bug: `src/aeat/domain/deadlines/_engine.py:474` (`compute_obligation_schedule` → `engine.compute(profile, today.year, today=today)`). Single-producer consumers to keep consistent: `src/aeat/application/state_projection.py:491` (as-of-today projection — leave on `today.year`) and `src/aeat/application/workflow/_engine.py:422` (the FILE/VERIFY gate — the explicit-target FILE branch re-scopes to the target period's year).
- Gate A abort: `src/aeat/application/workflow/_engine.py:455` (`obligation is None` → `NO_PENDING_OBLIGATION`) and `:477` (`obligation.closes_on < today` → `DEADLINE_PASSED`); abort enum `src/aeat/application/workflow/_models.py:129`.
- Gate B blocker emission: `src/aeat/application/calculations/_cross_period_clean_state.py:1026` (`_filing_external_evidence_blockers`, the `MISSING_AEAT_ACCEPTANCE` / `MISSING_EXTERNAL_EVIDENCE` / `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` emission at line 1033) and the locally-clean tier added alongside it; finding routing in `src/aeat/application/modelo/_verification_actions.py` (`_cross_period_clean_state_findings`, the `_FIRST_FILER_CANDIDATE_BLOCKERS` precedent at line 609).
- Tests to extend/reconcile: `src/aeat/application/modelo/tests/test_local_cross_period_carry.py` (lines 176, 204, 215), and the two e2e files (`test_e2e_ledger_m130_quarters_to_m100_annual.py`, `test_e2e_ledger_m303_quarters_to_m390_annual.py`).

### Gate A target plumbing (confirmed at HEAD)

The FILE gate already RECEIVES the explicit target — no plumbing is missing. `WorkflowEngine.run_for_period` (`src/aeat/application/workflow/_engine.py:178`) passes `target_modelo=modelo, target_period=period` (lines 225-226) straight into `_stage_computing_deadlines` (line 270). So Decision A is a single localized change: in that stage, when `target_modelo`/`target_period` are present, compute the schedule for `target_period.year` rather than letting `compute_obligation_schedule` derive `today.year`. The CLI entry point is `aeat app modelo work file` at `src/aeat/entrypoints/cli/_modelo_work_verification_cli.py:412` / `:465`, which calls `file_modelo_revision`; CLI test surface `src/aeat/entrypoints/cli/tests/test_modelo_work_ux.py:294` and the file-flow support harness `src/aeat/application/modelo/tests/_file_flow_support.py:506`. The extemporáneo / non-official-local-chain operator strings are authored only through the locale CLI (`aeat-locales-cli`), never hand-edited.

### Grounded mechanism confirmations

Two mechanisms the decisions rest on were read at HEAD and confirmed:

- **Decision B keeps the grant open via existing severity logic.** `_classify_verification_outcome` (`src/aeat/application/modelo/_verification_actions.py:1502`) returns `(COMPLETE, granted=True)` whenever no finding is `BLOCKING`. A WARNING-severity advisory is not blocking, so downgrading the cross-period `CROSS_PERIOD_DEPENDENCY_UNCLEAN` (BLOCKING) to a non-official-local-chain ADVISORY (WARNING) is sufficient to let verify grant and export proceed — no change to the classifier is required, only the finding's kind/severity for the locally-clean case in `_cross_period_clean_state_findings`.
- **Decision A's marker and its legal authority already exist.** The `Recovery` model (`src/aeat/domain/deadlines/_models.py:768`) carries `still_filable=True`, a resolved `recargo_band`, `legal_ref`, and a runnable `next_command`, and is already built for OVERDUE obligations by `_overdue_recovery_or_none` (`src/aeat/domain/deadlines/_engine.py:349`, bands in `_recargo.py:125`). Its docstring states the binding principle — "art-27 self-assessments remain admissible past the original deadline; the surcharge is the only consequence" (Ley 58/2003 art-27). That is the legal authority that a late LOCAL `work file` is admissible: Decision A records this existing `Recovery` onto the FILE step details (`workflow/_engine.py:480`-`504`) rather than aborting `DEADLINE_PASSED`.
- **Decision B's locally-clean facet mirrors an existing pattern.** The pre-activity suppression facet is the template: `NoPriorObligationProvenance` enum (`_cross_period_clean_state.py:130`), the facet field on `CrossPeriodDependencyEvidence` (`:337`), and the clean facet-stamped row builder `_suppressed_pre_activity_evidence` (`:540`). The new `non_official_local_chain` facet follows the same shape — a typed marker that yields a clean (advisory-only) evidence row — so the tier addition is idiomatic, not a new mechanism.

### Blast-radius completeness (all three C0 sub-defects, one observation)

A completeness sweep confirms the two decisions cover all three cross-period sub-defects with no third code path:

- **One observation feeds both carry origins.** The M130/M303 carry uses the `previous_filing` resolver; the M100 fold-in uses the `relation_prefill` resolver (`src/aeat/application/calculations/_relation_prefill.py`). Both read the SAME local observation store: `resolve_relations_from_local_store` (`_relation_prefill.py:125`) calls `repository.load_observation(...)` (line 84), and `RelationPrefillSourceResolver.resolve` (line 342) delegates to it. The `app_filing` observation `work file` persists therefore satisfies BOTH the `previous_filing` carry and the `relation_prefill` fold-in — Decision A's single change unblocks all three.
- **Decision B's facet is origin-agnostic.** The clean-state graph evaluates both `PREVIOUS_FILING_BINDING` and `REGISTRY_RELATION` origins, and the pre-activity suppression it mirrors is explicitly uniform across both origins (`partition_cross_period_requirements_by_activity_start`). The locally-clean tier therefore covers the M100 fold-in dependency and the M130/M303 carry dependency uniformly.
- **The reconcile path is the official-evidence boundary and stays out of scope.** `aeat app modelo reconcile pull` / `reconcile file --file` (`src/aeat/entrypoints/cli/_modelo_reconcile_cli.py`) import an AEAT justificante (official evidence). Decision A relaxes ONLY the local `work file` (app_filing) path; reconcile remains the legitimate route to upgrade a local chain to official evidence, and Decision B's official-evidence blockers stay BLOCKING for it. No reconcile change is in scope.

### Semantic-uniqueness verification (no duplicate mechanism)

A functionality-cluster sweep (`vaultspec-rag search … --type code`, paired with `rg`) confirms each decision is semantically unique and reuses, rather than duplicates, existing surfaces:

- **Decision A introduces no parallel late-filing mechanism.** No code path today allows `work file` past a closed window — the only existing handling is the `DEADLINE_PASSED` abort (`workflow/_engine.py:497`) and a recargo NOTICE on the calculate path (`_modelo_rendering.py:223`, `test_modelo_calculate_recargo_notice.py`, legal `lgt-autoliquidacion.toml`). Decision A REUSES that infra (the `Recovery` marker and the art-27 admissibility grounding) and removes only the abort; it does not add a second recargo model or notice surface.
- **Decision A's year basis is already an accepted pattern.** `_RevisionDeadlineWindowChecker.is_window_open` (`src/aeat/application/modelo/_workflow_gate.py:183`) already computes the schedule for `period.year` (the target period's year), while the single-producer `compute_obligation_schedule` (`src/aeat/domain/deadlines/_engine.py:442`) is the ONLY site hardcoding `today.year`. Decision A aligns the FILE gate's explicit-target branch with the window-checker's existing `period.year` semantics; the projection (`state_projection.py:491`) legitimately keeps `today.year` (what is pending now). The fix removes a latent inconsistency rather than inventing a computation.
- **Decision B is structurally parallel to the existing cross-period bypass, not a duplicate.** `_cross_period_clean_state_findings` (`src/aeat/application/modelo/_verification_actions.py:657`) already contains a tiered "unclean-at-verdict can be non-blocking under a typed condition" shape: the iva-wallet decision bypass (`_iva_wallet_decision_covers_cross_period_dependency`). Decision B's locally-clean tier slots in as a SIBLING condition in the same loop and reuses the established advisory-finding pattern (`unstamped_revision_advisory`, `operator_declared_suppression_advisory`) and the facet shape (`NoPriorObligationProvenance`). It is more disclosing than the wallet bypass — it emits a visible advisory rather than a silent `pass` — so it does not weaken `no-silent-under-declaration`.
- **The two bypasses do not collide.** The wallet bypass is scoped to M303 compensación with an authoritative `aeat_wallet` / `taxpayer_override` decision; the locally-clean tier is general and fires only when the sole blockers are the official-evidence delta over an `app_filing` chain. For an M303 compensación dependency with a wallet decision the wallet path governs; otherwise the locally-clean tier (advisory) governs. They are disjoint conditions on the same evidence row.

This sweep confirms the implementation is correct (aligns with existing accepted patterns) and semantically unique (no duplicate late-filing or non-official-acceptance mechanism is introduced).

## Implementation outcome (recorded post-execution)

This ADR proposed two decisions; the implementation, driven on `chore/eliminate-shims`, accepted Decision A and **declined Decision B** in favour of the stricter safety posture. Recorded here so the document matches the shipped code.

- **Decision A — IMPLEMENTED and green** (commit `6e635f566` plus the workflow-gate WIP it finalised). A late LOCAL `work file` for an explicitly targeted, closed-window obligation that genuinely existed is admitted (extemporánea, con recargo) and persists the `app_filing` carry observation; the FILE-gate obligation schedule resolves in the target period's filing year (guarded against `NoDeadlineWindowsError` → `NO_PENDING_OBLIGATION`); the submission filing-window preflight is skipped for the local FILE purpose. Net effect: the cross-period **carry value now flows** — the M130 1T→4T cumulative chain computes and folds into M100 0604, the M303 compensación reaches casilla 110. Proven green by `test_e2e_ledger_m130_quarters_to_m100_annual.py` and `test_local_cross_period_carry.py`. The 3 workflow-test reds this surfaced (`test_gate_aborts_when_projection_lacks_the_target`, `test_deadline_passed_via_run_for_period`, `test_verify_reaches_done_for_a_closed_filing_window`) are fixed; `test_engine.py` is 47/47.

- **Decision B — DECLINED by the implementers.** The locally-clean tier (admit a complete `app_filing` chain to verify/export with a non-blocking advisory) was NOT adopted. The implementers chose to KEEP the cross-period clean-state gate BLOCKING on non-official evidence, encoded deliberately in `test_verify_gate_blocks_chain_carrying_non_official_prior_year` (docstring: "This is the correct refusal, not a defect... per `local-filed-observations-are-non-official-evidence` and `aeat-safety-legal-gates`"). This is a sound, more-conservative reading of the safety rules than Decision B's advisory-with-disclosure: a dependent period whose upstream is local-only `app_filing` is refused verificado-completo, so its `.boe` export still requires real external AEAT evidence (justificante / CSV register / live capture).

- **The residual product question (deferred, operator-owned).** Decision A makes the cross-period *calculation* reachable but, under the declined Decision B, a late filer still cannot *export* a dependent period's `.boe` from a local-only chain — the gate refuses without official evidence. Whether to (a) keep this conservative gate (the implemented choice), or (b) revisit Decision B's admit-with-advisory to make dependent-period export reachable for genuine prior-year reconstructions, is an operator product decision, not a code defect. The implemented choice is internally consistent and green; this ADR records both the proposal and the implementers' divergence so the decision is auditable.

## Implementation outcome — update (Decision B implemented, refined same-year scope)

Superseding the "Decision B declined" note above: Decision B was subsequently implemented in a **refined same-year scope** that reconciles the reachability goal with the implementers' anti-laundering safety decision. Committed as `84add274d`.

- **What landed.** A SAME-FILING-YEAR cross-period dependency satisfied by a present, value-consistent, revision-confirmed locally-filed (`app_filing`) chain whose ONLY blockers are the official-evidence delta is admitted: the official-evidence-delta blockers are cleared (the row becomes clean) and a non-blocking `non_official_local_chain_advisory` is surfaced. A WARNING advisory keeps the verify grant open (`_classify_verification_outcome`), so the within-year reconstruction can reach verify/export. Sites: `_cross_period_clean_state.py` (facet + `_relax_same_year_local_chain` + verdict property), `_verification_actions.py` (advisory emission).

- **Why this is safe — the same-year scope.** The implementers' core safety decision was the **cross-YEAR** anti-laundering case (`test_verify_gate_blocks_chain_carrying_non_official_prior_year`, M100/2024 folding an unevidenced prior-*year* M100/2023). That test STAYS GREEN: the relaxation fires only for same-filing-year dependencies, so a cross-year non-official prior still blocks. `operator_manual` sources, value/revision divergence, and missing observation/filing keep their blockers. The `app_filing` source_kind stays non-official (never added to `_OFFICIAL_SOURCE_KINDS`); only the LOCAL verify/export path is relaxed, never an AEAT-acceptance assertion. This is strictly narrower — and safer — than the original unscoped Decision B, and it preserves `local-filed-observations-are-non-official-evidence` for the cross-year laundering case the rule was authored to prevent.

- **Net reachability.** A within-year quarter chain (e.g. M130 1T→2T→3T→4T of the year being reconstructed) is now reachable to export with disclosure; the M100 annual that folds a prior-YEAR return still requires that prior year's official evidence. The earlier "residual product question" is thereby resolved by a scoped middle path rather than left open.

- **Verification.** C0 surface 88/88 green (clean_state 34, local_carry 5, e2e 2, engine 47), including the cross-year safety canary. The owned size-budget ratchet on `_cross_period_clean_state.py` (SPLIT-CANDIDATE) was bumped 1265→1300 for the feature addition.
