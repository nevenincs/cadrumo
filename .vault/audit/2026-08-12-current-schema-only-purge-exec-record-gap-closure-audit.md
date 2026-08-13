---
tags:
  - '#audit'
  - '#current-schema-only-purge'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d62f6b2755109397fe22c0f8d03820a9d126a7cc89b13bfd205de274d99bb293'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# `current-schema-only-purge` audit: `exec record gap closure`

## Scope

The plan reads 42 of 42 checked at HEAD, but thirteen checked Steps (`W02.P06.S18`,
`S19`, `S20`, `S41`; `W03.P07.S27`, `S30`, `S31`, `S34`, `S36`, `S38`, `S39`, `S40`,
`S42`) carry no exec record. This audit does not backfill any of them. For each it
establishes whether standing evidence exists elsewhere in the vault, and where none
exists, obtains fresh evidence against the row's OWN cited verification target (a
named test file, or a direct code inspection where the row cites files rather than a
test) so the gap is closed with real signal rather than left as a bare absence. No
production file was changed. No exec record was authored for any of the thirteen.

The thirteen ids above were re-derived directly from
`vaultspec-core vault plan status 2026-08-10-current-schema-only-purge-plan`
immediately before writing this audit, not carried forward from an earlier paraphrase:
`S18, S41, S19, S20, S27, S30, S31, S34, S36, S38, S39, S40, S42`, thirteen entries, set-
identical to the list above.

**Backfilling an exec record for any of the thirteen was considered and rejected.**
This audit's author did not perform the work behind these rows and cannot attest to it
first-hand; writing a Step Record for work witnessed only after the fact would present
borrowed evidence as an author's own account, which is the same category error S37's
grounding decline just refused in the other direction (declaring a fact the tree cannot
support). The sanctioned remedy, used here, is this close audit recording the gap and
what would discharge it -- never a fabricated Step Record standing in for one.

**Per-row disposition**, in the three states the campaign owner asked this audit to
distinguish -- standing audit evidence exists; no evidence found anywhere in the vault
(fresh evidence obtained in this audit where the row names a checkable target); or
evidence exists elsewhere under a different name:

| Step | State | Where |
|---|---|---|
| S18 | no vault evidence; fresh test evidence obtained here | `test_master_key_file_fallback.py`, 25 passed |
| S19 | no vault evidence; fresh test + code evidence obtained here | `test_manifest_io.py`, 22 passed; `key_schedule` confirmed mandatory by inspection |
| S20 | no vault evidence; fresh test evidence obtained here | `test_manifest_io.py`, 22 passed (same run as S19) |
| S27 | no vault evidence; fresh test evidence obtained here | `test_prorrata_regularizacion.py`, 18 passed |
| S30 | evidence exists elsewhere, under S42's name | `2026-08-11-current-schema-only-purge-s42-operator-manual-audit` and its closure review scrutinize and remediate S30's own gate file without naming S30 |
| S31 | no vault evidence; fresh test evidence obtained here | `test_observations_repository_roundtrip.py`, 18 passed |
| S34 | no vault evidence; fresh test evidence obtained here | `test_complexity_allowlist.py`, 7 passed |
| S36 | standing audit evidence exists | `2026-08-11-current-schema-only-purge-s36-activity-start-audit`, PASS verdict |
| S38 | no vault evidence anywhere; fresh code-inspection evidence obtained here, and a residual gap found | `SecureObjectRepository.save` inspected directly; see finding below |
| S39 | no vault evidence; fresh test + code evidence obtained here | `test_observation_evidence_displacement_guard.py`, 8 passed |
| S40 | no vault evidence anywhere, and fresh evidence obtained here is NEGATIVE | `test_iva_wallet_blocked_decision_integration.py`, 5 of 6 failed |
| S41 | no vault evidence; fresh test evidence obtained here | `test_master_key_file_fallback.py`, 25 passed (same run as S18) |
| S42 | standing audit evidence exists | `2026-08-11-current-schema-only-purge-s42-operator-manual-audit` (findings) + `-s42-closure-review-audit` (remediation confirmed, close recommended) |

Only `S36` and `S42` carry a standing audit under their own name; both are excluded from
the findings below. `S30` is evidenced only by inference through a record naming `S42`.
The remaining ten have no vault record of any kind and are covered by fresh evidence
obtained directly in this pass.

## Findings

### exec-record-gap-master-key-kdf | low | S18/S19/S20/S41 have no record but their own cited tests pass now

Four `W02.P06` rows (`S18` file-fallback KDF-marker refusal, `S19` mandatory
`key_schedule`, `S20` manifest-read proof, `S41` path-redaction on the KDF refusal)
cite `test_master_key_file_fallback.py` and `test_manifest_io.py`. Both pass at HEAD:
25 passed and 22 passed respectively. Direct inspection of
`BucketManifest.key_schedule` in `_manifest.py` confirms it is a required field with no
default, matching `S19`'s claim exactly. No exec record exists for any of the four.

### exec-record-gap-prorrata-unblocked | low | S27's cited test is green though the row still reads as ADR-blocked

`S27`'s own text says it is "BLOCKED ON the ADR amendment" and does not state the
amendment landing resolved it. `test_prorrata_regularizacion.py` passes 18/18 at HEAD.
The amendment referenced is the accepted `2026-08-10-current-schema-only-purge-adr`,
already in this plan's `related:`. No record captures that the block lifted.

### exec-record-gap-carry-gate-evidenced-indirectly | low | S30 has no dedicated record but is evidenced through the S42 audit pair

`S30`'s static gate is `src/cadrumo/tests/test_observation_carry_ingress_caller_gate.py`,
which passes 4/4 at HEAD. The gate's two weaknesses recorded against `S42`'s scope in
the operator-manual audit (`non-normalizing-census`, a rogue literal-`False` caller
passing undetected; `production-scan-boundary`, the scanner not covering
`entrypoints`) are exactly `S30`'s gate, and the closure-review audit records both
remediated ("scans the complete `src/cadrumo` production package," "requires the
discovered caller set to equal the reviewed population"). `S30` is therefore evidenced,
but only by inference through a record that names `S42`, not itself.

### exec-record-gap-evidence-displacement-precursor | low | S31's cited roundtrip passes and the new field is present

`S31` cites the decision roundtrip in `application/calculations/tests`; the closest
match, `test_observations_repository_roundtrip.py`, passes 18/18. The
`local_evidence_found_but_unusable` field `S31` describes adding is present on the
reconciliation decision and threaded through `_iva_wallet_gate.py` as the row
describes. No exec record exists.

### exec-record-gap-complexity-allowlist | low | S34's cited gate passes

`dev/audit/tests/test_complexity_allowlist.py` passes 7/7 at HEAD, consistent with
`S34`'s own detailed narration of the stale-key/inherited-member distinction. No exec
record exists; the row's prose is the only account of the two wrong resolvers it says
were caught before shipping.

### exec-record-gap-s38-severity-unrecorded-but-answerable | medium | S38's own severity-deciding question is unmeasured in the vault, though code inspection answers it

`S38` is a measurement-only row (no test cited, matching the shape of the recorded
`S32`/`S33` rows) whose stated purpose is to decide whether the encrypted secure-object
substrate versions an overwritten key before any remedy is chosen. No exec record
answers it. Direct inspection of `SecureObjectRepository.save` /
`_save_internal` in `adapters/persistence/storage/sql/secure_objects.py` shows a plain
HMAC-keyed upsert with no history retention: `save`'s own docstring states "upsert one
byte payload keyed by a natural string id." This confirms `S38`'s DESTRUCTIVE branch
("the official evidence is DESTROYED by an ordinary operator command and the loss is
unrecoverable") over its shadowing branch. `S39`'s built refusal is the shape that
branch calls for, so the row's implicit conclusion is corroborated, but the question
S38 exists to answer was never itself recorded as answered, and S39 only covers the
official-eviction edge -- an ordinary same-kind overwrite (app_filing over app_filing,
operator_manual over operator_manual) still silently destroys the prior row with no
guard, which is the part of S38's original scope neither S38 nor S39 closes.

### exec-record-gap-evidence-displacement-guard | low | S39's build is real, tested, and located exactly where its own text requires

`test_observation_evidence_displacement_guard.py` passes 8/8. `_refuse_official_evidence_displacement`
lives inside `prepare_observation_envelope` in `_observations_repository.py`, the one
method every writer (operator verb, live capture, local filing) calls before any write
is prepared -- matching S39's explicit requirement that the guard sit on a check both
disjoint write paths call, before a transaction is opened. Both locale keys
(`observation_displaces_official_evidence_app_filing`,
`observation_displaces_official_evidence_manual`) are present and real (not
self-referencing placeholders) in all four catalogues. No exec record exists.

### exec-record-gap-s40-cited-test-currently-red | high | S40's own cited integration test fails 5 of 6 cases at HEAD

`S40`'s implementation is real: `_blocked_refusal` in `_iva_wallet_gate.py` maps each
blocking `IvaCompensationDecisionReason` to its own reason code and its own
`application.iva_wallet.decision_reason.*` locale key, replacing the bare `"blocked"`
literal the row describes. But its own real-behaviour test,
`test_iva_wallet_blocked_decision_integration.py`, fails at HEAD: 5 of 6 cases red, 1
passed. The four parametrized `test_blocked_wallet_divergence_refuses_real_modelo_303_calculation_before_persisting_revision`
cases and the single `test_persisted_blocked_wallet_decision_is_replayed_by_modelo_303_calculation`
case assert `pytest.raises(..., match="wallet_higher")` (and sibling short codes
`wallet_lower`, `wallet_stale`), and the raised message is instead the untranslated
locale KEY `application.iva_wallet.decision_reason.wallet_local_recurrence_divergence`.

BOTH vocabularies are live in the tree, which rules out "the test names a code that no
longer exists" as the explanation. `wallet_higher`, `wallet_lower` and `wallet_stale`
are real, current values of `decision.divergence` in
`domain/iva_compensation/_reconciliation.py`, still computed and still carried in the
raised exception's `context["divergence"]`. `_blocked_refusal` reads a DIFFERENT field,
`reason_identity`, and maps every one of those three divergence values to the single
`WALLET_LOCAL_RECURRENCE_DIVERGENCE` reason. The three-way distinction is not gone from
the data; it is gone from the operator-facing reason/message the refusal now speaks
through, and `context["divergence"]` is not established anywhere in this pass to be
rendered to an operator rather than carried only as internal diagnostic evidence.

This audit does NOT decide which of two readings is correct, and states both because
choosing wrong in either direction loses something real. Reading one: the test is
stale, written against a vocabulary the reason-identity refactor deliberately retired
in favour of one shared divergence reason, and aligning the test to
`wallet_local_recurrence_divergence` is the fix -- correct ONLY if an operator reading
a blocked wallet decision never needed to know WHICH of the three shapes it hit, merely
that it diverged. Reading two: the distinction is load-bearing for the operator -- a
wallet reading higher than local, lower than local, and stale are three different
situations calling for three different operator responses -- in which case collapsing
them at the reason-identity layer is a real regression and the TEST is right; the fix
is adding the three distinct reason identities `_blocked_refusal` does not yet have,
not editing the test. Nothing in this codebase surface was read closely enough in this
pass to settle which population the live CLI/export callers of this refusal are in;
that is exactly the judgement call the finding exists to flag rather than resolve.
Either way this is a real defect sitting on a currently checked plan row with no exec
record and no audit; this is the one finding in this audit that is not merely an
absent record.

## Recommendations

**The campaign is structurally complete (42 of 42 checked) but is NOT honest-closed
until this audit is treated as its record of the gap.** A checkbox and a matching
Step Record are not the same claim, and thirteen rows here carried only the former.
This audit is the sanctioned discharge the standing rule names for exactly that state
-- it does not retroactively make the thirteen rows "recorded", it records that they
are not, with what is known about each in their place.

For the record: `W03.P07.S37`, the one row that was genuinely open before this audit,
closed on a grounding DECLINE rather than a build. No Certificado de Situación Censal
(G313) specimen exists anywhere in this tree, and the bundled consolidated RGAT text
does not itemize the certificate's physical fields, so neither authority confirms the
document carries an alta date at all, let alone whether it would attach to the censal
registration or to the economic activity. Adding the parser field anyway would have
manufactured a shape no specimen supports and invited a caller to trust it; the row
was closed on that refusal, not on code.

Per-row discharge, so the next reader does not have to re-derive what each needs:

- `S18`, `S19`, `S20`, `S27`, `S31`, `S34`, `S39`, `S41` -- each has fresh passing
  evidence against its own cited target obtained in this audit (see Findings and the
  disposition table). Discharged by a short retrospective exec record citing that
  evidence, authored by whoever next touches the row -- never mechanically generated
  from this audit's text.
- `S30` -- discharged the same way, citing the `S42` audit pair as the evidence source
  rather than a fresh run of its own, since that pair already covers its exact gate
  file.
- `S38` -- discharged by recording the answer this audit obtained (the secure-object
  substrate does not version; overwrite destroys) AND opening a new row for the residual
  gap this audit found: an ordinary same-provenance overwrite (not an
  official-to-non-official downgrade) still silently destroys the prior observation with
  no read-before-write, no history, and no guard. `S39` never covered that edge.
- `S40` -- NOT dischargeable by a retrospective record; its own cited test is red. Needs
  a fresh pass that either updates `test_iva_wallet_blocked_decision_integration.py` to
  assert the real `wallet_local_recurrence_divergence` identity (if collapsing
  wallet-higher/lower/stale into one code was the intended remedy) or extends
  `_blocked_refusal` with the distinct codes the test's four parametrized cases were
  written to exercise (if the distinction is load-bearing for an operator reading the
  refusal). Do not close it by loosening the test's match to whatever currently passes
  without deciding which.
- `S36`, `S42` -- already discharged; no further action.
