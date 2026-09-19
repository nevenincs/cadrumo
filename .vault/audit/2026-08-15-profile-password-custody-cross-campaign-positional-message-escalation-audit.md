---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:10e04da5995cf820ead18941bbd6f76ac40b64e9ee62bfbd4a2ba009447ce0c3'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `cross campaign positional message escalation`

## Scope

This is an escalation, not a repair. It re-derives, at HEAD, the E_REHOMING_OWNER_CLOSED
population the rehoming ledger's validator reports for `error_code_default_recovery_rehoming.py`,
identifies the owning campaign, and states per closed step whether its checkbox is true,
narrower than declared, or unimplemented against its own declared scope. No plan row
outside this feature's own plan was edited, and no source producer was touched.

## Findings

### owning-campaign-identified | high | the rehoming module's plan authority is `2026-08-09-cli-action-envelope-hardening-plan`

`dev/quality/error_code_default_recovery_rehoming.py` hardcodes `_PLAN_PATH` to
`.vault/plan/2026-08-09-cli-action-envelope-hardening-plan.md`; every `owner_step` the
ledger cites is a Step id in that plan, not in this campaign's own plan. That is the
"owning campaign" the row names. This campaign's own `W04.P07.S70` triaged the ledger's
findings and reclassified the "closed-owner violation" code as "the second code is a
correct gate reporting a WRONG PLAN" -- a step marked complete while producers inside its
own declared scope were still unmigrated -- with one readiness-gate module cited as the
worked example. This escalation verifies that classification against current source and
sharpens it: it is not uniformly true of all nine steps.

### re-derived-figures | medium | current counts drift from the row's cited numbers, in both directions

Re-running the validator at HEAD (`validate_rehoming_ledger(load_rehoming_ledger())`)
reports 152 total findings, not 151: `E_REHOMING_FINGERPRINT_MULTISET` rose from 102 to
104, `E_REHOMING_ZERO_DISPOSITION` held at 6, and `E_REHOMING_OWNER_CLOSED` fell from 43
to 42 -- matching S70's own already-reclassified count of "forty-two plan-wrong" exactly,
even though the row still cites the pre-triage "forty-three." The tree moved between
measurements, consistent with S70's note that it did too between its two counts. The
`E_REHOMING_OWNER_CLOSED` population -- the one this escalation is chartered to examine
-- is stable at 42, spanning exactly nine distinct owner Steps: `S96` (24), `S38` (5),
`S89` (4), `S101` (2), `S81` (2), `S82` (2), `S94` (1), `S104` (1), `S114` (1). All nine
are in `2026-08-09-cli-action-envelope-hardening-plan.md` and all nine are checked `[x]`.
`S96`'s 24 matches the row's "twenty-four of the forty-two" exactly.

### readiness-gate-module-confirmed | critical | `_profile_readiness_gate.py` carries migrated and unmigrated raise sites side by side

`src/cadrumo/application/modelo/_profile_readiness_gate.py` raises
`ModeloProfileReadinessError` at seven sites. Two -- line 351 and line 367 -- pass a
runtime-built English sentence (`message`, an f-string assembled at line 394, e.g.
`f"Modelo {modelo_code} is not applicable to the active profile: {applicability.reason}"`)
as the first positional constructor argument, which is exactly the pattern `str(exc)`
prefers and which keeps a hardcoded English sentence alive in every locale. The other
five -- lines 479, 517, 538, 542, 578 -- pass only `translated_message=` and `context=`
keyword arguments, the migrated shape. This file is explicitly listed in `S96`'s own
declared scope. It is the "one readiness-gate module" the row and S70's record both
point to, verified directly against current source rather than trusted from either.

### S96-genuinely-unmigrated | critical | `S96`'s 24 findings trace to real in-scope positional constructor sites across most of its declared file list

Beyond `_profile_readiness_gate.py`, `S96`'s declared scope still authors raw sentences
positionally at, among others: `_calculate_input.py:1095,1412`;
`_local_observation_actions.py:159`; `_m036_lifecycle.py:333`;
`_prior_domiciliation.py:47,53,75,81,91,114,123,144,155,193,224` (nine of nine
`ModeloPriorDomiciliationElectionRefusedError` sites, all positional);
`_profile_binding.py:334,338,1126,1136,1153,1196,1208` (seven of seven);
`_projection.py:482`; `_registry_helpers.py:391,468,561,570,576`;
`_review_package_feedback.py:256,345,358`; `_review_package_signing.py:236`;
`_selectors.py:393,470,702`; `_semantic_role_resolution.py:126`;
`_verification_actions.py:912`; `_work_addressing.py:143,149,371,626,683,779,997`;
`_workflow_gate.py:359`. Forty-seven in-scope positional constructor sites in total
against 24 distinct qualname findings -- this is not a stray straggler, it is most of the
declared scope's error classes never touched. `S96`'s checkbox is `recorded-but-not-implemented`
for the bulk of what it declares, not merely `delivered-narrower`.

### S81-S82-fully-unmigrated | critical | `S81` and `S82` show zero migration inside their own declared scope

`S81` (`src/cadrumo/application/review`) owns 25 constructor sites for
`EditParseError` (`_edit.py`, 12 sites) and `FilterParseError` (`_filter.py`, 13 sites);
every one of the 25 is positional -- 100%, not a partial migration. `S82`
(`src/cadrumo/application/storage_management`) owns 9 constructor sites for
`StorageReclaimRefusedError`/`StorageReclaimUnconfirmedError` in `_service.py`; all 9 are
positional. Both steps are `recorded-but-not-implemented` in the strict sense: the
checkbox claims a completed migration of a scope where verifiably nothing was migrated.

### S38-S89-S104-partial | high | `S38`, `S89`, `S104` are `delivered-narrower`: real migration landed, specific in-scope sites did not

`S38` (`src/cadrumo/application/ledger`) migrated most of its 40 owned constructor sites
but left 10 in-scope positional sites standing, confirmed at
`_aeat_record_projection.py:108`, `_evidence_draft.py:2023`, `_evidence_input.py:156`,
`_evidence_reference.py:230,256`, `_evidence_textlayer.py:91`,
`_filer_establishment.py:116,129`, `_llm_classification.py:300,348`. Read directly:
`_evidence_input.py:156` raises `PurchaseInvoiceEvidenceInputError` with an f-string
positional first argument alongside a keyword `precondition_verdict=`. `S104`
(`src/cadrumo/application/storage/calc_sheets`) left `_layout.py:165,173` positional for
`CalcSheetsEngineError` while its other owned sites are migrated. `S89`
(`src/cadrumo/entrypoints/cli/_config`) left `_profile_inspect.py:107,128` and
`_repair_profile.py:239` positional for `ConfigBoundaryError`; these three are `S89`'s
only genuine in-scope violation (see next finding for the other three).

### validator-conflates-shared-qualname-owners | critical | three of the nine findings are not checkbox lies -- they are a row-granularity artifact of the validator, not evidence against `S94`, `S101`, or `S114`

The validator's `require_open_owner` gate is computed once per historical qualname
(`authors_message = any(... for fingerprint in expected)`), then applied uniformly to
*every* ownership of that qualname, including ownerships whose own fingerprint is a
non-authoring `reference` or an already-migrated `constructor`. Three of the nine findings
are exactly this: the flagged step's own declared scope is fully migrated, and the actual
unmigrated site lives in a *different* step's scope inside the *same* governing plan --
one that is currently OPEN, not closed, so no checkbox is lying about it:

- `S94` (`src/cadrumo/llm`) owns keyword-only `PurchaseInvoiceEvidenceInputError`
  constructors (e.g. `_invoice_field_grounding.py:301`, `context=`/`precondition_verdict=`
  only). The qualname's positional site is `S38`'s `_evidence_input.py:156`, already
  counted above as a genuine `S38` violation.
- `S101` owns only two `KeyringUnavailableError` fingerprints, both `role = "reference"`
  in `_login_session.py:555,674` -- not constructors, so they author nothing. Every
  positional `KeyringUnavailableError` constructor (`_master_key.py`,
  `_acceleration_receipt.py`) is owned by `S70` -- "Migrate persistence adapter recovery
  producers... `src/cadrumo/adapters/persistence`" -- which is still open (`[ ]`) in
  `2026-08-09-cli-action-envelope-hardening-plan.md`. `S101`'s other finding
  (`ProfileRegistrationError`) shows the same shape: zero in-scope constructor sites.
- `S114` owns only `reference`-role `ConfigBoundaryError` fingerprints in `_errors.py`;
  the positional constructors are `S89`'s (already counted above as `S89`'s genuine
  violation).

The same mechanism separately implicates `S89`'s `BucketDeleteRefusedError` finding
(constructors owned by `S107`, "Migrate bucket-maintenance recovery producers," also open)
and `ModeloWorkRegistryYearMismatchError` co-attributed to both `S89` and `S96` (the
positional constructor at `_work_addressing.py:779` is `S96`'s, already counted there;
`S89`'s share of that qualname is not itself positional). So the effective genuine
in-scope-violation count for `S89` is one qualname (`ConfigBoundaryError`), not four.

## Recommendations

- Classification per step, using the row's own three-way frame:
  - `recorded-but-not-implemented` (checkbox claims completion; verifiably nothing or
    almost nothing in scope was migrated): `S81`, `S82`, and -- for the bulk of its
    scope -- `S96`.
  - `delivered-narrower` (real migration landed; specific named producers were left
    behind): `S38`, `S89`, `S104`.
  - `delivered-as-specified` for the step's own declared scope, mis-flagged by the
    validator's per-qualname coupling to a still-open sibling step: `S94`, `S101`,
    `S114`. Nothing in these three steps' own scope needs migration; the flag clears
    only when the sibling step (`S70` for `S94`/`S101`'s `KeyringUnavailableError`
    share, `S89` for `S114`, `S107` for `S89`'s `BucketDeleteRefusedError` share)
    finishes its own migration.
- This is the owning campaign's decision to make, not this campaign's: whether to
  reopen `S38`, `S81`, `S82`, `S89`, `S96`, `S104` against their genuine in-scope gaps,
  and whether to correct the validator's per-qualname `require_open_owner` coupling
  (documented above) so it stops attributing a sibling step's incompleteness to a
  step whose own share is done. Neither edit was made here.
- Bears on `W04.P07.S79` (extend open steps' declared scopes before regenerating): the
  `E_REHOMING_FINGERPRINT_MULTISET`/`E_REHOMING_ZERO_DISPOSITION` codes S79 targets are a
  distinct failure mode from `E_REHOMING_OWNER_CLOSED`, examined here. But the
  qualname-sharing conflation found above is a convergence hazard S79 should carry
  forward: extending an open step's scope does not, by itself, clear a shared-qualname
  finding against an unrelated closed step -- only finishing the open step's own
  migration does, so `S79`'s regeneration should not assume that closing scope gaps
  alone resolves every `E_REHOMING_OWNER_CLOSED` entry.
- Bears on `W04.P07.S71` (the analyser's guarded-variable-vs-string-literal export
  asymmetry): the per-qualname-versus-per-fingerprint granularity issue found here is a
  *different* rule shape than S71's export-resolution question. It is not S71's finding
  and is not resolved here; it is named so a future step can rule on it deliberately
  rather than by a widening amendment made in passing.
- `W04.P07.S78` can be marked complete: the escalation is delivered, evidence-bearing,
  and does not touch the owning campaign's plan or its source.
