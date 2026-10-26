---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:2a906bd6f4fb253aa97e6d0ba1737554847fcc2adbdeb1121751782528a95e83'
related:
  - "[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr]]"
---

# `registry-completeness-closure` audit: `S84 independent two-channel proof review`

## Scope

Read-only independent review of commits `b7852e8196` and `f5af07f91f` against the accepted S33 two-channel export-proof ADR, supporting research and decision review, plan row `W03.P05.S84`, and its execution record. The review used semantic discovery, whole-file and exact-symbol inspection, and a fresh-current-state check. It covers sole-writer/destination topology, dynamic refusal, value-independent conformance, secure source-owned replay, custody, receipt secrecy, test integrity, and plan integrity.

## Findings

### secure-replay-self-attestation | high | A caller-built public receipt can satisfy the secure channel without custody

Once S85 supplies conformance, a fabricated fresh provenance-matching receipt can therefore satisfy secure replay without approved source resolution or encrypted custody, contrary to S33.

### public-vector-self-classification | high | The value-independent channel admits taxpayer-capable models on its public vector

The asserted public classification at `:130` is only the required literal `non_sensitive_mechanism_vector`, and `STRICT_FROZEN_HIDDEN_INPUT_CONFIG` only suppresses invalid input in validation errors. The type boundary therefore cannot prevent a real taxpayer draft or producer snapshot from becoming a committed S85 vector, violating S33's value-independent and secret-free conformance constraint.

### legacy-proof-temp-output | medium | The remaining live-proof route will write an enrolled source-owned payload to plaintext temp storage

Its canonical entry tuple is currently empty, so no current secret is exposed, and S84's new consumer route itself avoids a file. Nevertheless this is still the live closure authority's export path; enrolling a source-owned entry there would violate secure-storage-only custody rather than refusing or routing via encrypted in-memory replay.

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
- `uv run --no-sync pytest -n 0 -q -m integration dev/registry/tests/test_filing_export_two_channel_proof.py` - `2 passed`.
- Focused Ruff over the committed S84 proof, adapter, storage, registry, and
  test surfaces passed.

### Recommendation

**FAIL at MEDIUM** pending a real source-pinned emitted-byte comparison. The
previous two HIGH findings and the legacy plaintext-temporary MEDIUM are
resolved. This review does not promote S84, S33, S85, or S86 to complete.

## Final residual-fix re-review - 2026-08-25

### Scope

Read-only final review of `dba75ffaa9` against the original findings in
`8fd32b7853`, the remediation review in `e738673a8d`, the accepted S33
ADR, the S84 execution record, and the canonical source surfaces. The review
uses the committed S84 snapshot. Later shared-worktree changes outside the
reviewed paths are not attributed to this result.

### Findings

### residual-probe-byte-verification | low | The previous MEDIUM is resolved by source-owned typed expectations before custody persistence

`FilingExportSourcePinnedProbeExpectation` is hidden typed source evidence:
it binds one `FilingExportOfficialProbe` to non-empty expected bytes with an
exact span-length validator. `FilingExportSecureReplayEvidence` requires its
ordered expectation probes to exactly equal the complete public provenance
probe tuple, whose existing validator already requires distinct,
non-overlapping spans. The expectation bytes exist only in the source-owned
replay evidence; the public request rejects their injection, and the public
receipt and encrypted custody record have no expectation field.

`FilingExportReplayCustodyRepository.persist_secure_replay` compares every
emitted byte slice with those typed expectations before constructing or saving
the all-true encrypted custody record. The same-length substitution regression
refuses `ABC` versus `ABD`. The exact proof, request, receipt, record, and
adapter sweep finds no path that serializes expected bytes to a public receipt,
request, log, or repository record.

The earlier caller-receipt HIGH, taxpayer-capable public-vector HIGH, legacy
plaintext-temporary MEDIUM, and residual source-pinned-probe MEDIUM remain
resolved. RAG discovery, whole-file review, and exact-symbol confirmation
continue to find one canonical `export_draft` writer route, the typed in-memory
secure destination, one encrypted replay-custody implementation, no accepted
caller receipt parameter, and no competing proof authority. Empty conformance
and secure-replay enrollment still refuses dynamically; S33, S85, and S86
remain open.

### Recommendations

PASS. Retain the exact ordered expectation coverage and same-length corruption
regression whenever a real source authority is enrolled. Do not expose expected
bytes outside source-owned transient evidence or treat S84 as S33/S85/S86
completion.

### Verification

- Focused proof corpus: 9 selected unit tests passed and 2 integration tests
  passed, for 11 proof tests.
- Encrypted storage namespace and taxonomy-lineage corpus: 49 passed.
- Scoped Ruff passed for the application proof, encrypted custody adapter,
  registry authority, and their focused tests.
- The final committed S84 source paths remained unchanged after
  `dba75ffaa9` during this review; concurrent profile/configuration WIP was
  preserved.
