---
tags:
  - '#audit'
  - '#export-publication'
date: '2026-07-24'
modified: '2026-07-24'
related:
  - "[[2026-07-17-export-publication-plan]]"
  - "[[2026-07-17-export-publication-adr]]"
  - "[[2026-07-17-export-publication-audit]]"
---

# `export-publication` audit: `Close honesty review`

## Scope

Fresh-context honesty review of the `export-publication` plan, which reports eleven of
eleven steps complete. The plan collapses the two CLI-owned writers for portable
profile export and the subject-access request onto one durable publication service
(`prepare_profile_export`, `publish_prepared_export`, `reconcile_prepared_exports`) in
`src/cadrumo/application/user_profile/_bundle_export.py` and its companion contract and
operation-state modules. This feature is GDPR-style profile-bundle portability and
right-of-access export, not the AEAT modelo filing exporter.

Scope correction before findings: the dispatch brief for this review asked that
particular attention go to `modelo-export-mirrors-official-structure` (offline
xls/Sheets/fichero-BOE parity, the completeness-manifest value-presence gate) and
`aeat-safety-legal-gates` (live AEAT submission prohibition), framing them as "the
campaign's whole point," and asked this reviewer to independently confirm a reported gap
in `dev/release/tests/test_publish_release_workflow.py`. Both are misdirected. Every one
of the eleven steps' scoped files sits under
`src/cadrumo/application/user_profile/`, `src/cadrumo/entrypoints/cli/_config/`,
`src/cadrumo/application/operator_surface/_risk_table.py`, or
`docs/reference/import-export-and-evidence.md`; none touches the registry, the modelo
export planner, the fichero-BOE writer, or any AEAT transport. `git log` for
`dev/release/tests/test_publish_release_workflow.py` shows its most recent commit
(`56d58d789b`, landed during this review) closes a finding named
`publish-guardrail-lost-its-non-vacuity-proof` against a *different* campaign
(`cli-authority-quality-backlog`); it is unrelated to profile-bundle export. This
reviewer independently confirmed the file now defines both `_BUILD_RUN_PATTERNS` and
`_PUBLISH_RUN_PATTERNS`, scanned per job, with over-match and under-match discrimination
proofs for each — the gap described in the brief is closed, but under a different
feature's close review, not this one. This mismatch is treated as a scoping note, not a
finding against the export-publication plan itself.

The reviewer re-read every plan step, its exec record, and the governing ADR and
mid-campaign continuous-gate audit; ran the real test suites the exec records cite
(`test_bundle_export.py`, `test_bundle_export_recovery.py`,
`test_profile_bundle_flow.py`, `test_classification_parity.py`,
`test_documented_command_conformance.py`, `test_parity.py`) sequentially against HEAD;
read `_bundle_export.py`, `_bundle_export_contracts.py`, and
`_bundle_export_operation.py` in full; and traced every caller of
`reconcile_prepared_exports` and `bundle_data_categories` project-wide. The review is
read-only; no production file was modified.

## Findings

### reconcile-safety-net-never-invoked | high | The crash-recovery mechanism S10/S11 built and proved is unreachable from any production caller

`reconcile_prepared_exports` (`src/cadrumo/application/user_profile/_bundle_export.py:216`)
is the sole function that clears an orphaned `PREPARED` operation, emits an owed
`PROFILE_EXPORTED` event for a durably-replaced-but-uncompleted bundle, and removes a
leftover cleartext `.export-tmp` staged file. A project-wide grep for
`reconcile_prepared_exports` finds exactly four hits: its own definition, the package
facade re-export in `__init__.py`, and its two call sites in
`test_bundle_export.py`/`test_bundle_export_recovery.py`. No CLI command, no
application-service composition, no startup hook, and no maintenance verb calls it
anywhere in `src/`. The two CLI commands that publish exports
(`src/cadrumo/entrypoints/cli/_config/_profile_bundle.py:154` and `:331`) call only
`export_profile_bundle`, never reconcile.

S10's own exec record already discloses this ("No production caller wires reconcile
yet, so the race was latent; the lock makes reconcile safe to call at any time"), and
S11's outcome claims the crash-recovery work "closes the un-audited-egress window ...
no durably-published bundle is left without its PROFILE_EXPORTED event after
reconcile." That claim is true only inside the test harness, where every test that
leaves a `PREPARED` journal calls `reconcile_prepared_exports()` itself (directly, or
in a `finally:` cleanup). In an actual operator session, a process crash between the
staged-temp fsync and the atomic replace (or between the replace and the completion
event) leaves the orphan journal and, in the pre-replace case, a `0o600` cleartext
staged-temp file containing the full profile bundle sitting on disk under
`<storage-root>/profile-export-operations` indefinitely — nothing in production will
ever call reconcile to clean it up or complete its audit trail. This is the same
"safety net built and switched off" shape `no-dormant-source-resolvers` names for a
different subsystem: the mechanism is correct and its tests are real and non-tautological,
but it is dead code from the operator's perspective. Neither the plan nor the
mid-campaign audit tracks a follow-up step to wire it (e.g. a `config profile export
reconcile` maintenance verb, or a call at CLI startup/next-export time analogous to how
`config_reset_status` self-heals on next access).

### category-derivation-still-a-static-field-map-with-no-exhaustiveness-gate | high | The "never a static list" claim is only half true, and the CLI notice over-promises completeness on top of it

S01 and S07 both claim `bundle_data_categories` derives categories "from the actual
bundle schema ... never a static list," explicitly framed as fixing the CLI's prior
hand-maintained personal-data category list that could "silently drift from what the
bundle actually contains." The implementation
(`src/cadrumo/application/user_profile/_bundle_export_contracts.py:37-43,109-125`) does
iterate the real `UserProfilePortableExport.model_fields` at call time (so a *removed*
field cannot leave a stale category behind), but the field-to-label mapping itself,
`_CATEGORY_BY_BUNDLE_FIELD`, is a hand-maintained five-entry `dict[str, str]` in the
same module. A field present on the live schema but absent from that dict is silently
dropped from the walrus comprehension (`if (category := _CATEGORY_BY_BUNDLE_FIELD.get(field_name)) is not None`)
with no error, no warning, and no test failure. `UserProfilePortableExport`
(`src/cadrumo/domain/user_profile/_portable_export.py:158-200`) currently has two
fields, `carried_objects` and `coverage_manifest`, that are *not* in the static map and
are legitimately covered instead by the separate `coverage_manifest.carried_namespaces`
derivation — so today's five financial-history fields happen to be exhaustively
covered. But that coverage is a coincidence of the current field set, not a structural
guarantee: any future top-level field added directly to the strict-frozen schema
(rather than routed through the generic secure-object carry surface) silently vanishes
from `data_categories` unless a human remembers to add it to the map in the same
change.

The only test that touches this,
`test_data_categories_are_derived_from_serialized_bundle_fields`
(`src/cadrumo/application/user_profile/tests/test_bundle_export.py:166-184`), is
tautological with respect to exhaustiveness: its comprehension at lines 178-182 is
`{_CATEGORY_BY_BUNDLE_FIELD[field] for field in type(bundle).model_fields if field in
_CATEGORY_BY_BUNDLE_FIELD}` — it filters to fields already in the map before checking
anything, so it cannot fail if a schema field is missing from the map. No test asserts
`set(UserProfilePortableExport.model_fields) - {metadata fields} - {carried-namespace
fields}` is a subset of `_CATEGORY_BY_BUNDLE_FIELD.keys()`.

This raises the severity above a plain "static list" nit because the CLI notice this
data feeds is a completeness claim to a GDPR data subject:
`_build_sar_catalogue_notice` (`src/cadrumo/entrypoints/cli/_config/_profile_bundle.py:202-228`)
tells the subject-access requester "This archive holds every personal-data category
kept for the profile. The exact categories are listed in the `data_categories` field of
this response" (locale key `cli.config.profile.sar_catalogue_info`). If a future
financial-history field is added to the schema without a matching
`_CATEGORY_BY_BUNDLE_FIELD` entry, that field's data ships inside the exported bundle
bytes while `data_categories` — and the notice asserting "every ... category" — silently
omit it, contradicting `no-silent-under-declaration`'s spirit for a right-of-access
disclosure rather than a tax filing.

### plan-frontmatter-omits-own-adr | low | The plan does not relate to its own grounding decision record

The plan's `related:` frontmatter lists six documents (the shared cli-authority-verb-conformance
ADR/research/reference/plan/audit plus this feature's own mid-campaign audit) but not
`[[2026-07-17-export-publication-adr]]`, the thin grounding ADR authored specifically
for this plan under the rescope. The ADR does link back to the plan
(`.vault/adr/2026-07-17-export-publication-adr.md:9`), so the graph edge exists in one
direction only. This is the identical pattern the `duplication-evidence-repair` close
review found on a sibling successor plan from the same rescope
(`2026-07-22-duplication-evidence-repair-close-honesty-review-audit.md`,
`plan-frontmatter-omits-own-adr`), suggesting it may be systemic across the six
rescoped successor plans rather than incidental to this one.

### s07-plan-step-cites-a-nonexistent-file | low | Step S07's scope path was never a real file and the plan text was never corrected

Plan step `S07` cites `src/cadrumo/entrypoints/cli/_config/_profile_export.py` as its
scoped file. That path does not exist; the substantive change landed in
`src/cadrumo/entrypoints/cli/_config/_profile_bundle.py`. The exec record for S07
honestly discloses the divergence and states it was "flagged to the coordinator," but
the plan document itself (which an auditor reading only the plan, not every exec
record, would trust) still names the wrong file. No functional gap: the real file was
independently confirmed to contain the claimed change (the derived-categories notice,
no static list, no direct target write).

### no-silent-under-declaration-and-live-submission-checks-pass | confirmed | No under-declaration or live-AEAT-submission concern applies to this feature

Verified directly rather than assumed, given the brief's framing: this campaign has no
formula, casilla, or verification-gate surface (`no-silent-under-declaration` and
`aeat-safety-legal-gates` govern tax-calculation and AEAT-transport code this feature
never touches), and the sensitive-financial-data-secure-storage rule is satisfied by
design — the docs table and the export purpose model both explicitly exclude
attachment evidence bytes from the portable bundle, and the equal `handoff=True` risk
classification (S08, confirmed live in `_risk_table.py:137,153`) gates the CLI's own
sensitivity warning before a cleartext, vault-external artifact is produced. These are
not gaps; they are confirmed non-findings recorded so the verdict below is not read as
having skipped them.

### structural-claims-independently-confirmed | confirmed | The core durable-publication mechanism, the facade discipline, and the locale/risk/docs gates hold at HEAD

Re-run at HEAD, sequentially, outside the default `-m unit` filter (these suites carry
`pytest.mark.integration`): `test_bundle_export.py` + `test_bundle_export_recovery.py`
(16 passed, 135.9s, including the real-child-process forced-crash proofs at
`os._exit(91)` and the real SQLite constraint-trigger event-failure proof — no mocks,
stubs, or tautologies observed), `test_profile_bundle_flow.py` (13 passed),
`test_classification_parity.py` (7 passed), `test_documented_command_conformance.py`
(352 passed), and `src/cadrumo/tests/test_parity.py` (33 passed, locale catalogues,
current working tree). `service-imports-via-top-level-reexports` holds: every
cross-package caller of the export symbols goes through
`cadrumo.application.user_profile`'s `__init__.py` facade; the only private
`_bundle_export*` imports are intra-package (`__init__.py` itself and the package's own
`tests/`), which the rule permits. The previously-dead `COMPLETED` operation-state enum
from the mid-campaign audit's LOW-2 is now genuinely read and written by
`publish_prepared_export` and `reconcile_prepared_exports`. The event-failure contract
rewrite in S11 left no stale reference to the superseded
"restores_preexisting_target" test. Six post-closure commits
(`a3a0219bd5`, `c2fb2a71da`, `b02597ce85`, `b08aab0743`, `8bba418fcf`, `590c6cc28f`)
touched the export files after the plan's last step landed; all are narrowly-scoped,
well-documented repo-wide hygiene-gate fixes (hardened-writer routing, hashing
canonicalisation, lazy-import allowlisting, format/type gates, a UTF-8 constant, a
semgrep convention) rather than undisclosed feature work, and none is itself
unaccounted-for scope creep worth a separate finding.

## Recommendations

Wire `reconcile_prepared_exports` to a real production trigger before treating the
crash-recovery half of this feature as operationally complete: either a maintenance CLI
verb (e.g. under `config profile`) an operator or support workflow can invoke, or a
call at the start of the next `export_profile_bundle` for the same profile/target,
mirroring the self-healing pattern `config_reset_status` already uses for the sibling
reset journal. Until one exists, the S10/S11 guarantees are proven-but-inert.

Close the exhaustiveness gap on `_CATEGORY_BY_BUNDLE_FIELD`: add a test asserting every
non-metadata, non-carried-namespace field of `UserProfilePortableExport.model_fields`
has an entry in the map (fail loudly on a schema field the map does not cover), so a
future field addition cannot silently narrow the GDPR disclosure notice's "every ...
category" claim. Rewrite
`test_data_categories_are_derived_from_serialized_bundle_fields`'s schema-coverage
assertion to iterate the full field set rather than pre-filtering to already-mapped
fields.

Add `[[2026-07-17-export-publication-adr]]` to the plan's `related:` frontmatter, and
correct step S07's scope path to `_config/_profile_bundle.py`. Given the identical
frontmatter gap was already found on the sibling `duplication-evidence-repair` plan
from the same rescope, a single sweep across all six rescoped successor plans would be
more efficient than fixing this one in isolation.

Re-scope future dispatch briefs for this feature away from
`modelo-export-mirrors-official-structure` / fichero-BOE completeness and toward the
GDPR/profile-portability rules that actually govern it
(`sensitive-financial-data-secure-storage-only`, `no-silent-under-declaration` as
applied to disclosure completeness, `single-subject-mutation-is-idempotent-guarded` for
the export operation's clock-free id derivation) — the name collision between
"export-publication" (this feature) and the unrelated release/distribution
"publish"-named work is a recurring source of misdirected review scope and is worth
naming plainly to whoever assigns the next review here.

**Verdict:** not structurally complete. Eleven of eleven steps have real exec records
backed by real, non-tautological, passing tests, and the majority of claims in this
plan hold up under independent re-verification — this is materially better ground truth
than the campaigns the honesty-review discipline was written against. But two concrete,
high-severity gaps survive: the crash-recovery mechanism the plan spent two full steps
(S10, S11) building is unreachable from any production code path, and the
schema-derived category claim central to S01/S07 is a narrower, still-static mapping
with no test guarding its exhaustiveness, feeding a CLI notice that promises GDPR
completeness it cannot structurally back. Both are fixable in a small follow-up rather
than a re-open of the whole plan, but the plan should not stand at "11/11, done" without
a tracked follow-up step for each.
