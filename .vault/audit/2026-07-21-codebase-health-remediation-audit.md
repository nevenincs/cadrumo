---
tags:
  - '#audit'
  - '#codebase-health-remediation'
date: '2026-07-21'
modified: '2026-07-21'
related:
  - "[[2026-07-17-adr-code-reconciliation-audit]]"
---

# `codebase-health-remediation` audit: `codebase health remediation campaign`

## Scope

This document records the multi-agent remediation of every `just check-*` and
`just audit-*` finding standing on `main` on 2026-07-21. The campaign covered
five gate families — complexity, duplication, security, facade and import
hygiene, and types — plus the pre-existing defects those gates surfaced along
the way. It is the campaign record of what was executed, what was deliberately
tolerated and why, and what remains open at close.

The sole gate-grade RED at open was complexity: 87 new or regressed hotspots
against the checked-in baseline. Duplication stood at 62 clone clusters and
0.38% duplicated lines. Every claim below is grounded in the commit it names.

## Findings

### complexity-work-packages | high | eleven designed work-packages, ten landed and verified at HEAD

The complexity surface was partitioned into eleven work-packages, each a pure
structural decomposition asserting zero behaviour change.

WP1 config-reset, `9851e08ae8`: `ConfigResetOperation._validate_operation`
D(29) to A(1) via one dispatching model validator over four named helpers, the
class D(30) to B(7); `ConfigResetTarget._validate_target_state` C(14) to three
helpers, class C(15) to A(5); `verify_deletion_ownership` C(15) to A(1) over
four module-private ownership checks.

WP2 auth application, `d6e1dbf7a3`: `build_auth_readiness` D(30) to B(7);
`_build_auth_cleanup_intent` D(23) to A with the operation-id join material
byte-identical; `_apply_auth_cleanup_intent` C(18) to A; `_probe_certificate_bundle`
C(14) to B. A follow-up type fix landed as `e03b9674b8`.

WP3 auth adapters, `a9e22536b0`: a new `_session_probe.py` owns one shared
`run_authenticated_landing_probe`, retiring the near-byte-identical `_verify_in_work`
clone that Cl@ve Móvil and Cl@ve Permanente each carried. The Móvil selector-page
click becomes an `on_landing` hook; Permanente passes `None`. The
`persisted_session_reason_code` substring ladder became an ordered dispatch
table with specificity order preserved.

WP4 bucket maintenance, `f764cc53de`: `BucketMaintenanceService._delete_locked`
D(22) to A(2) across six single-concern helpers, with the sequenced
crash-consistency order, the reset-owned no-ambient-route rule, error strings,
and event payloads byte-preserved.

WP5 calculation actions, `e3caca846b`: the caller-override reconciliation
algebra was lifted out of `calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`
into a frozen `_CallerOverrideReconciliation` and a pure helper, taking the
driver D(30) to C(14). The diagnostics filtering stays set-identical, which is
what keeps the no-silent-under-declaration contract intact.

WP6 ledger LLM and CLI, `095e5eb914`: `_ledger_split_llm` D(29) to B,
`ledger_saturate_llm` D(29) to C(11), `ledger_classify_llm` C(19) to B or
better. `_command_matches_current` D(28) to A was resolved deliberately as
per-side projection tuples rather than a shortened boolean chain: the
projections are proven identical position-for-position, so a future model field
omitted from the idempotency match is one greppable site rather than a silent
field-drop — a field-drop there would be a silent under-declaration on a
guarded single-subject mutation.

WP7 modelo cluster, `0a4f780988` with type follow-up `ad7243b332`:
`derive_calculation_revision_id` D(21) to B(7), with the digest pinned from
HEAD *before* the refactor and a sanctioned id-pinning test added over the
optional branches, proving byte-identity of the content address;
`validate_m210_agrupacion_renta_rows` D(21) to A(1);
`resolve_profile_sourced_bindings` D(21) to A(5);
`project_modelo_100_from_m130` D(24) to B(8).

WP8 CLI shell, `9c4c7aab79`: `command_error_boundary` cognitive 38 to 10, the
five-arm except ladder collapsed to an ordered exception-to-projection dispatch
tuple walked in declaration order, which reproduces the former subclass
specificity ordering exactly; `_root` cognitive 22 to 9;
`_register_profile_import_command` cognitive 28 to below threshold;
`_formula_operation_label` reduced to two module-level maps.

WP9 locales, `27e877575d`: `LocaleManager.audit` C(20) to A, `_echo_audit`
C(11) to A, `tr` C(14) to B(8) with strict-placeholder enforcement moved onto
the strict path only.

WP10 core infrastructure, `1110a630d1`: `acquire_lock` C(20) to A(2) and
`release_lock` C(11) to A(4) with the retry, steal, and stale conditions, the
poll intervals, and the condition-variable protocol unchanged;
`await_cancellation_complete` and `close_async_resources` decomposed with the
bare re-raise left in the caller so exception chaining survives;
`_save_internal_in_session` C(12) to A(5) with the single-session transaction
spine and CAS conflict raises unchanged; `read_sealed_archive` C(15) to A(5)
with no version tolerance widening.

WP11 periphery landed in three explicit-pathspec commits. `ddeb55719a` covers
the outbound and inbound adapters: `LLMCache.prune` C(14) to B and
`UsageRecorder.prune` C(11) to B, whose twin retention ladders were
deliberately *not* cross-extracted because they read different row shapes;
`list_drive_folder_documents` C(11) to B with the paging state machine moved
into a generator that the caller fully consumes, so the Drive scope refusal
still surfaces from the same call; `DefaultBrowserSession.close` C(12) to B
with the aggregation contract preserved, including the re-raise of a cancelled
error after the runtime is stopped; `OfxProvider.ingest` C(20) to B(6) and its
class C(12) to B(8).

`d5a365ae08` covers application-layer periphery:
`_classify_irnr_income_transaction` C(11) to B with guard order preserved and
every aggregation issue constructed verbatim; `_seed_inputs_into_sheet` C(11)
to B; `WorkflowEngine._stage_building_draft` C(17) to B with the stage's
started stamp threaded through so every workflow step keeps its original
timing.

`72acbf4262` covers the entrypoints: `_prune_orphan_defs` C(16) and cognitive
26 to B, split into explicit mark and sweep phases over the fixpoint graph
walk; `enforce_required_runtime_cohort` C(11) to B by extracting cohort
probing and refusal rendering, with the stderr wording and the exit code
unchanged; and `__getattr__` in the profile facade D(24) and cognitive 23 to
A(2) and cognitive 1, the PEP-562 ladder replaced by a declarative
name-to-module table resolved through one import hop, with laziness, the
`__all__` set, and the byte-identical attribute error all preserved.

This paragraph corrects an earlier draft of this record, which stated WP11 had
not landed. That draft was committed on a stale read: the three commits are
ancestors of the commit that carried it, so the work was already at HEAD when
the claim was written. The re-read-HEAD-before-reporting discipline exists for
exactly this failure, and it was not followed here.

### complexity-tolerated-hotspots | medium | four hotspots tolerated on stated rationale

Four surfaces were examined and deliberately left alone. `build_server` in the
MCP entrypoint carries cognitive 109, but it is a registration shell summing
roughly fifteen individually readable SDK handlers that share session state;
decomposing it needs a session-state carrier plus handler factories, which is
protocol-boundary churn for no per-path readability gain. The one real
function-level hotspot in that same file, `enforce_required_runtime_cohort`,
was remediated under WP11 in `72acbf4262`, so the tolerance is scoped to the
registration shell alone rather than to the module. `LocalHttpBoundary.route`
in the browser test harness is a route table. `domain/transactions/_models.py`
carries its maintainability grade from boundary-contract validators.
`locales/_modelo_manager.py` has no function-level hotspot at all — only a
module-level maintainability index.

### duplication-batch-a-and-b | high | 62 clusters at 0.38% reduced to 13 at 0.08%

Batch A landed seven groups: `8bf229716e` storage and inbound adapters,
`73947e5e5f` config CLI, then the modelo-work CLI across `492982ddf2`,
`3f65c60d88`, `2705d3adf9`, and `959eae6e77` behind a new private
`_modelo_work_options.py`; `2bd50567ea` registry CLI, `0e1b7e7465` filed-data
capture, `df9524b3ac` ledger invoice, and `2193e6c9bb` sede, attachments, and
registry. Batch B landed `73b545cb74`, `97a204e5be`, `f6a6aa35eb`,
`0aa88fd351`, `c3a8a16598`, and `3b5f93f90b`.

The final adjudication `e9a3c35abe` overturned two prior KEEP verdicts on
merit rather than on effort. The ledger review-filter cluster had been read as
"thin emit tails"; on re-reading it is a real `LedgerReviewFilterSpec` to
`LedgerReviewQuery` field projection, extracted as `ledger_review_query_for_spec`
into the upstream module so `ledger list` narrowing and the `ledger review`
verb resolve the same filter clauses through one projection. The verification
DI fan-out had been recorded DIVERGENT-KEEP, but the repository already carries
a `_WizardDeps` frozen-dataclass precedent for exactly that shape; a
`_VerificationDeps` was added and passed to the two private sub-registrars,
leaving the public registrar's explicit keyword signature untouched.

The audit gate at close reports 13 clones and 0.08% duplicated lines, matching
the residual register below row for row.

### duplication-residual-register | info | thirteen surviving clusters, recorded to prevent re-litigation

The following is the residual register verbatim, as sites, lines, and
rationale. It exists so a future duplication sweep does not re-open settled
adjudications.

1. `_aeat_nif_iva_oracle` and `_groi_oracle` | 28 | Identical module import
   prologue of two parallel per-oracle modules; imports cannot be shared.
2. `_modelo_work_revision_payloads` and `_modelo_work_wizard_payloads` | 17 |
   Two OutputSchema pydantic models sharing 18 fields under different heads;
   only dedup is a shared base class — forbidden for parallel pydantic models;
   field order is part of the output-schema contract.
3. `_modelo_amend_wizard_cli` and `_modelo_work_wizard_cli` | 22 | Identical
   signature and target-resolution prologue but different deps bundles
   (`_AmendWizardDeps` vs `_WizardDeps`); unifying needs a cross-variant
   Protocol carrying an `Any` seam.
4. `_ledger_llm_cli` internal | 28 | classify vs saturate sibling entry points
   share a 13-param signature; bodies already share `_llm_classify_prologue`;
   deduping the signature needs a public-signature change.
5. `domain/attachments/_service.py` | 41 | `add_attachment` vs
   `add_attachment_bytes` public twins; persist core already extracted;
   residual needs a forbidden public-signature change.
6. `_calendar_models` | 12 | Two pydantic models' period serializer and
   validator boilerplate; bodies already delegate; only unification is a base
   or mixin.
7. `_calculation_source_staging` | 13 | Wrapper-vs-delegate parameter
   mirroring; a pass-through wrapper necessarily mirrors its delegate.
8-9. `_remote_state_models` twice | 12, 14 | Parallel capture-report models
   sharing 13 fields under different discriminator heads; shared base class
   forbidden.
10. `application/ledger/_models.py` | 11 | `ManualLedgerTransaction` vs Patch:
    required-with-validators vs all-optional; a base class would blur that
    distinction.
11. `_renta_gasto_ledger` and `_renta_income_ledger` | 15 | Per-family
    aggregation module import prologue; scaffolding, not logic.
12. `_impatriado_income_ledger` and `_renta_income_ledger` | 29 | Verified by
    read: import prologue plus enum and model scaffolding, not a
    classification predicate.
13. `diagnostics_run_health` | 7 | Different target types, discriminators and
    field sets; shared part is six trivial aggregate expressions.

Eleven of the thirteen survive because they are parallel pydantic models,
per-family module scaffolding, or public sibling signatures — deduplicable only
via a shared base class or mixin, or via a public-signature change, both
forbidden by the design and by the substitutability pre-filter the swarm audit
cadence rule mandates. That pre-filter exists because a prior promotion pass
carried a 96% false-positive rate. Thirteen is the honest floor for the current
design, not a shortfall.

### security-directory-mode-false-positives | medium | both findings were false positives; a missing test was added

Both `_DIRECTORY_MODE` security findings were false positives. The
reset-operation and profile-export journal repositories chmod their external
journal roots to `0o700`, already the tightest mode a traversable directory
admits. The generic insecure-file-permissions rule compares numerically —
`0o700` is 448, `0o644` is 420 — rather than by bitmask, so it fires on the
most restrictive possible value. The remediation `590c6cc28f` converged both
sites on the explanatory `# nosemgrep` convention the master-key layer already
established, and added the POSIX-gated real-behaviour test that was missing on
the bundle-export side; the reset-operation side already carried the
equivalent assertion.

### facade-fingerprint-retarget | medium | private-submodule import retargeted without weakening invalidation

The compiled-cache loader fingerprint imported private submodules to hash the
defining source of the embedded schema-core types, breaching the
public-facade rule for dynamic import targets. Commit `07040a4a80` reshaped
the module set into public-module and symbol pairs and resolves each symbol's
true defining file through `inspect.getsourcefile`, so the import target names
the public facade while cache invalidation still follows the private
definition. An anti-regression test asserts the resolved files are still the
private defining modules rather than the package `__init__`. A type narrowing
in that test followed as `05a0a757ac`.

### gates-caught-campaign-introduced-regressions | high | four type regressions were introduced by the refactors and caught by the types gate

The refactors introduced four type-narrowing regressions, each caught by the
types gate rather than by review. `e03b9674b8` restored precise types on two
WP2 helper boundaries that had been widened to `object`, reintroducing a
TypedDict for the preflight-field splat and the exact `CertificateHealth` type
for bundle-health classification. `ad7243b332` restored a genuinely optional
`str | None` fingerprint on the WP7 `_ProfileFacts` carrier, which had been
over-narrowed to `str` — the correct fix was to match the source contract, not
to assert an invariant the code never held. `05a0a757ac` replaced an implicit
narrowing with an honest assert. `f3f86709a4` fixed the WP6 extraction
`_validate_classify_llm_options`, which refused a `None` transaction id but
returned `None`, so its own guarantee was invisible at its only call site and
an unnarrowed `str | None` travelled onward; the guard now returns the
validated id.

This is the load-bearing observation of the campaign: pure-structural
decomposition is not type-neutral in practice. Three of the four regressions
share one shape — an extraction that widens or drops a type its inline
predecessor carried implicitly — and none was caught by review. The gate is
what made them visible.

### pre-existing-cli-integration-failures | high | thirteen integration-lane failures on main, two of them genuine production bugs

Thirteen CLI integration-lane failures were standing on `main` and were
invisible to the unit lane. Two were genuine production localisation defects.
`26512d41a4`: a `config switch` that cannot unlock its target raises the
master-key refusal after the lifecycle span has unwound and restored the
previous active profile, so the failure was rendered in the *source* profile's
language; the target-bucket language activation that used to cover this was
dropped when the switch moved into `_custody.py`, and is now restored by
pinning the render locale to the target bucket's plaintext output-language
hint, which is readable without the DEK. `a6b2d56713`: Typer vendors its own
Click fork whose integer parameter type is named `int` rather than `integer`,
so after the Click 8.4 and Typer 0.27 upgrade an invalid integer option
rendered an English "is not a valid int." tail through an otherwise localised
message; both spellings are now localised.

The remaining eleven were honest test corrections rather than production
defects: the clock pinned in the backlog future-window test `a4edc34ace`, the
cold-start budget derived from a bare-interpreter baseline `93e28744d5`, the
help-metavar assertions updated for Typer 0.27 rendering `1fc121af31`, and the
non-active profile rename routing assertion corrected `1f45c1a76a`.

### silently-disabled-types-gate | high | deleted stubs had disabled half the types gate

`156c4e1dee` restored `stubs/playwright_stealth` and `stubs/pypdfium2`, which
had been deleted as collateral of a working-tree checkpoint on 2026-07-01. The
project configuration had referenced the `stubs/` path all along, so their
absence silently disabled the ty half of the types gate for three weeks
without any failure being reported.

### vault-check-inflated-by-stray-virtualenv | medium | a 1.2 GB virtualenv inside .vault scored third-party markdown as vault documents

A stray virtualenv created inside `.vault/` on 2026-04-29 was inflating
`vault check` to 236 phantom errors by scoring third-party site-packages
markdown as vault documents. Removing it left exactly one real error, which
was then resolved. The gate had been effectively unreadable for as long as the
virtualenv sat there.

### vault-sweep-collateral-restored | high | rule-cited governance ADRs restored, remaining deletions ratified

The two bulk vault sweeps of 2026-07-17 had collaterally deleted governance
documents that project rules cite by name. Seventeen documents were restored
byte-exact from the pre-sweep commits, and the remaining deletions of the 251
swept documents were ratified with recorded evidence. The disposition is held
in the 2026-07-17 ADR-code reconciliation audit, which this document links as
its companion record.

### residual-at-close | high | complexity gate still RED at 13 new or regressed hotspots

Measured at HEAD `72acbf4262` — that is, with all eleven work-packages landed —
the duplication gate passes at 13 clones and 0.08%. The complexity gate remains
RED: 13 new or regressed hotspots, 468 baselined entries allowed, and 42
baseline entries now resolved. Both gates were re-run after WP11 landed and
returned identical figures, so the residual below is a post-WP11 measurement.
That is down
from 87 at open, so the campaign closed roughly 85% of the surface, but the
gate is not green and this document does not claim it is.

Six of the thirteen sit in files the campaign touched. `close_async_resources`
in `src/cadrumo/core/async_cleanup.py` is the clearest campaign-introduced
regression: WP10 reduced its cyclomatic grade but its cognitive complexity now
measures 32, above the threshold — the decomposition traded one metric for the
other. The maintainability index of `src/cadrumo/application/config_reset.py`
(WP1) and `src/cadrumo/application/auth/_operator.py` (WP2) both newly grade B,
the arithmetic consequence of splitting large functions into many helpers in
the same module. `_m369_unresolved_oss_source_finding` was improved from C(19)
to C(11) by WP7 but remains above the C threshold and so is newly listed.
`_calculate_modelo_revision_with_trusted_mesh_sources` and
`RegistryQueryService._resolve_revision` are newly listed at C(11) in
campaign-touched files.

Seven are pre-existing debt in files the campaign never opened:
`LocalHttpBoundary.route` at D(21), `EvidenceValidator._source_text` at C(11),
`Preflight.check` regressed to C(12), `_prepare_certificate_secret_mutation` at
cognitive 24, the two tolerated maintainability-index entries, and
`build_server` at cognitive 109 — whose regression from 105 predates this
campaign, since that file has no commit newer than 2026-07-18.

A types-gate burndown of 21 diagnostics was in flight at the time of writing.
Several of those are pydantic discarded-extra-argument diagnostics in tests,
which may indicate vacuous assertions rather than mere type noise; that
possibility is unresolved and should not be assumed benign.

## Recommendations

Treat the campaign-introduced complexity regressions as in-scope rather than
deferring them. `close_async_resources` at cognitive 32 and the two new
maintainability-index B grades were produced by this campaign's own edits;
under the in-scope-regression discipline they belong to it. The specific
question the async-cleanup case raises is whether an extraction that lowers
cyclomatic while raising cognitive complexity is a net improvement at all, or
whether that surface wants a different decomposition shape.

Resolve the types-gate burndown before any green claim, and specifically
determine whether the pydantic discarded-extra-argument diagnostics indicate
tests asserting against silently-dropped fields. A test that passes because an
argument was discarded is a vacuous assertion, which is a correctness finding
rather than a typing one.

Check every extraction for a type the inline predecessor carried implicitly.
Four of this campaign's own regressions were of that one shape, and none
surfaced in review — a helper boundary widened to `object`, an optional
narrowed to non-optional, a guard whose refusal guarantee did not travel with
its return value. A decomposition pass over typed code should run the types
gate as a step, not as a post-hoc check.

Run the fresh-context honesty review before this campaign is declared
structurally complete, per the campaign-close honesty-review rule. This
document is the driving agent's own record and is therefore exactly the
artefact that rule requires an independent reviewer to read against HEAD. The
WP11 correction recorded above is a live example of why: a status claim in
this document was wrong within minutes of being written because the
underlying work landed between the check and the commit, and only a re-read
of HEAD caught it.
