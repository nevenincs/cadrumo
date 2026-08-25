---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:b4ada917b9d5be9869eaff728d5bb55971fa3656a8d564d76c03934a84570b34'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr]]"
---
# `registry-completeness-closure` audit: `S84 independent two-channel proof review`

## Scope

Read-only independent review of commits `b7852e8196` and `f5af07f91f` against the accepted S33 two-channel export-proof ADR, supporting research and decision review, plan row `W03.P05.S84`, and its execution record. The review used semantic discovery, whole-file and exact-symbol inspection, and a fresh-current-state check. It covers sole-writer/destination topology, dynamic refusal, value-independent conformance, secure source-owned replay, custody, receipt secrecy, test integrity, and plan integrity.

## Findings

### secure-replay-self-attestation | high | A caller-built public receipt can satisfy the secure channel without custody

`CanonicalTwoChannelFilingExportProofAuthority.assess_for` in `dev/registry/filing_export_proof.py:185` selects a member of the caller-supplied `secure_replay_receipts` tuple and checks only freshness and public provenance before returning a complete proof. `FilingExportSecureReplayReceipt` in `src/cadrumo/application/filing/_export_proof.py:286` is directly constructible, with every substantive outcome claim defaulting to `True`; the contract test constructs one directly. Whole-tree confirmation finds no concrete `resolve_secure_replay` or `persist_secure_replay` implementation, only the protocols at `src/cadrumo/application/filing/_export_proof.py:231` and `:273`. Once S85 supplies conformance, a fabricated fresh provenance-matching receipt can therefore satisfy secure replay without approved source resolution or encrypted custody, contrary to S33.

### public-vector-self-classification | high | The value-independent channel admits taxpayer-capable models on its public vector

`FilingExportConformanceRequest` at `src/cadrumo/application/filing/_export_proof.py:120` carries `ModeloDraft`, `FilingProducerSnapshot`, and arbitrary dictionary values; those models contain taxpayer tax identifiers, identity facts, accounts, and casilla values. The asserted public classification at `:130` is only the required literal `non_sensitive_mechanism_vector`, and `STRICT_FROZEN_HIDDEN_INPUT_CONFIG` only suppresses invalid input in validation errors. `FilingExportConformanceVector` at `dev/registry/filing_export_proof.py:148` adds no independent classifier, provenance source, or serialization guard. The type boundary therefore cannot prevent a real taxpayer draft or producer snapshot from becoming a committed S85 vector, violating S33's value-independent and secret-free conformance constraint.

### legacy-proof-temp-output | medium | The remaining live-proof route will write an enrolled source-owned payload to plaintext temp storage

`FilingExportLiveProofEntry` in `dev/registry/filing_export_proof.py:103` accepts a draft, producer snapshot, and accepted payload digest, while `_execute_export` at `:481` writes the rendered result through `TemporaryDirectory`. Its canonical entry tuple is currently empty, so no current secret is exposed, and S84's new consumer route itself avoids a file. Nevertheless this is still the live closure authority's export path; enrolling a source-owned entry there would violate secure-storage-only custody rather than refusing or routing via encrypted in-memory replay.

## Recommendations

- Replace caller-supplied replay receipts with a custody-backed resolver that retrieves and validates an encrypted internal record or opaque, verifiable attestation before projecting its secret-free receipt. Add a forged-receipt refusal test and real secure-storage roundtrip plus mutation tests.
- Split public conformance inputs from taxpayer-capable filing models. Derive a restricted non-sensitive specimen type or approved public data source, make classification independently verifiable, and prove committed vectors cannot serialize taxpayer identity, values, accounts, payloads, digests, paths, or byte extents.
- Fail closed on source-owned entries in the legacy live-proof route and reserve filesystem temporaries for independently classified public conformance only. Route any real replay through the typed in-memory destination and encrypted custody.
- Do not represent S84 as a completed secure source-owned replay boundary until these findings are resolved and verified under S85/S86's dynamic enrollment and gate work.

## Remediation re-review - 2026-08-25

### Scope

Read-only re-review of the requested remediation snapshots `44a055dcaf` and
`7f1c8bc266` against this audit, the accepted S33 two-channel ADR, research,
decision review, plan row `W03.P05.S84`, and its execution record. The review
used fresh Vaultspec-RAG discovery, whole-file reads, exact-symbol searches,
and focused current-head gates. It is anchored to the committed snapshots:
uncommitted changes that appeared on the same S84 files while the review was
in progress are not attributed to this result.

### Finding disposition

- **Resolved - `secure-replay-self-attestation` (previous HIGH).** The canonical
authority accepts source and custody ports, not a caller-provided public receipt;
`prove_secure_export_replay` drives source resolution, the sole
`export_draft` writer through the in-memory destination, custody persistence,
and public projection. The constructor regression rejects the removed
`secure_replay_receipts` parameter.
- **Resolved - `public-vector-self-classification` (previous HIGH).** Public
`FilingExportConformanceRequest` and
`FilingExportConformanceVectorEvidence` contain only coordinate,
authority/provenance, and mechanism identity. Draft, producer, dictionary,
election, and product values are excluded from those public vector models and
are only transient authority-materialized render inputs, as the accepted ADR
allows.
- **Resolved - `legacy-proof-temp-output` (previous MEDIUM).**
`LiveFilingExportProofAuthority.proof_for` raises before any export for an
enrolled legacy entry; its module has no temporary-directory, output-path, or
`export_draft` route. The sole remaining `TemporaryDirectory` is the
ADR-permitted public-conformance mechanism path.

### secure-replay-source-probe-self-attestation | medium | Custody attests source-pinned probes without verifying their bytes

At `7f1c8bc266`, `FilingExportReplayCustodyRepository.persist_secure_replay`
checks only that every public provenance probe ends within the emitted payload,
then persists `source_pinned_probes_passed=True`. `FilingExportOfficialProbe`
contains an identity, offset, and length but no expected bytes, and neither the
source protocol nor the custody boundary supplies a separately verified
source-pinned byte expectation. A same-length payload with altered bytes at
every stated probe span can therefore receive the public
`source_pinned_probes=True` attestation. This is not a failure of encryption,
receipt opacity, or the source/custody invocation path; it makes that specific
receipt claim unverified.

The remediation must pass source-owned, non-persisted expected bytes (or an
equivalent independently derived verifier) for each declared probe, compare
the emitted spans before sealing the encrypted record, and retain a
same-length-corruption refusal test. The expected bytes must remain absent from
public receipts, repository artifacts, and logs.

### Commit attribution and verification

`44a055dcaf` directly carries the S84 proof boundary in the filing proof
contract, registry authority, storage namespace, encrypted replay adapter, and
corresponding focused tests. Its operator-output, wizard, and JSON-contract
documentation edits are unrelated shared-tree capture. Its filing conftest,
runtime, draft-identity test, and modelo calculation-route test changes are
also independent test/runtime work, not evidence for the S84 remedy.
`7f1c8bc266` confines its relevant change to the filing proof contract,
registry regression, and contract test.

- Vaultspec-RAG semantic discovery plus whole-source and exact `rg` sweeps
  found one canonical `export_draft` writer path, no accepted
  `secure_replay_receipts` input, one encrypted custody implementation, and
  no competing proof authority.
- `uv run --no-sync pytest -n 0 -q src/cadrumo/application/filing/tests/test_export_proof_contracts.py src/cadrumo/adapters/persistence/profile/tests/test_filing_export_replay_custody.py dev/registry/tests/test_filing_export_two_channel_proof.py` - `8 passed, 2 deselected` by the unit lane.
- `uv run --no-sync pytest -n 0 -q -m integration dev/registry/tests/test_filing_export_two_channel_proof.py` - `2 passed`.
- Focused Ruff over the committed S84 proof, adapter, storage, registry, and
  test surfaces passed.

### Recommendation

**FAIL at MEDIUM** pending a real source-pinned emitted-byte comparison. The
previous two HIGH findings and the legacy plaintext-temporary MEDIUM are
resolved. This review does not promote S84, S33, S85, or S86 to complete.
