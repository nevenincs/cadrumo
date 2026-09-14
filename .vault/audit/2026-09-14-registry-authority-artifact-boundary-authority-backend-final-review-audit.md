---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:53aec85a1fc296ea77bc9216453b421e74a6322b238df52c5deef5b4fd4afcfe'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-adr]]"
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference]]"
---
# `registry-authority-artifact-boundary` audit: `authority backend final review`

## Scope

Formal review of the live authority-backend implementation against the accepted immutable-publication ADR, its remediation plan, and the post-delta architecture reference. The review covers the canonical runtime authority, artifact codec and immutable schema projections; full development compilation and validation; source, compiler, component, and payload identity; evidence closure; final publication admission; and removal of facts-only publication. Independent development-tooling and corpus-pruning changes are outside scope.

## Findings

### final-receipt-cutover | high | Resolved

The first review found that `write_authority_artifact` invoked its `before_replace` callback before staging and fsyncing the full artifact, leaving a large interval in which inputs could change after the final receipt check.

Resolution: the writer now encodes and admits the candidate, stages and fsyncs those exact bytes through `hardened_staged_publication`, then invokes the final receipt callback immediately before `publication.publish()`. The detector proves a callback refusal preserves the previous artifact.

### distinct-build-identities | high | Resolved

The first review found that the publisher computed separate source and compiler receipts but discarded them from the artifact, preserving only one combined identity and no component dependency identity.

Resolution: artifact v5 requires a typed `AuthorityBuildIdentity` carrying source-manifest, compiler/schema, and whole-generation component-dependency digests. It validates their composition, persists them canonically, exposes recorded and candidate identities through currency reporting, and keeps the outer payload digest separate.

### evidence-text-cache-identity | high | Resolved

The first review reproduced a fresh evidence validator returning normalized text from superseded bytes after an equal-length source replacement with restored modification time.

Resolution: normalized source-text cache keys now include the catalogue-verified source SHA-256 and the manual sidecar digest in addition to extraction contract and metadata. A regression detector validates old required text is rejected and replacement text is read after a metadata-preserving rewrite.

### runtime-artifact-cache-identity | high | Resolved

The first review reproduced Windows serving a cached authority after equal-length in-place corruption and restored modification time because `st_ctime` is creation time on Windows.

Resolution: runtime file admission now includes Windows `FILE_BASIC_INFO.ChangeTime` through `file_change_time_ns`, while other platforms retain `st_ctime_ns`. A Windows-capable detector corrupts a cached artifact with equal length and restored mtime and requires the next read to fail integrity admission.

### manual-sidecar-input-closure | high | Resolved

The review found that conformance consumed `manual_corpus_text` sidecars while the source-evidence receipt walked only the main corpus tree. Those sidecars could therefore affect admission without affecting source identity or the final receipt.

Resolution: source evidence discovery now includes both `corpus` and `manual_corpus_text` trees, and source identity hashes their root-relative paths and byte-exact contents.

### parsed-toml-cache-identity | high | Resolved

The review found that an uncached registry walk still delegated each source row to `toml_file_fingerprint`, which omitted content digests for the editable checkout when it was reached through `bundled_path`. A same-length TOML rewrite with restored mtime could preserve the parsed and compiled cache key even during publication.

Resolution: every developer TOML fingerprint now includes its content digest. The obsolete bundled stat-only predicate and its contradictory documentation were removed. The detector proves equal path, length, and mtime still produce a changed fingerprint after content replacement.

### unvalidated-authority-type-laundering | high | Resolved

The review found that diagnostic fallback loaded raw tree data and passed it to `ValidatedRegistryAuthority.from_validated_components`, temporarily granting the full runtime authority type without registry-wide conformance even though the final returned projection was narrow.

Resolution: diagnostic fallback now receives `StructuralRegistryComponents`, derives static classification from modelos and catalogues directly under candidate fact scope, and never constructs `ValidatedRegistryAuthority` after strict conformance fails. The validated path wraps the same narrow data-only derivation.

## Validation

- Final focused artifact, runtime corruption, identity currency, publication, evidence-cache, and TOML collision selection against the republished v5 artifact: 64 passed in 45.70 seconds.
- The committed v5 artifact currency check against the final live inputs: 1 passed.
- Final tracked v5 generation `28abbb04db05ae702a5b69f9f93c98a3f19821c1f0b2f927f630fba70bc0f616`: the full integrity CLI exited 0 against live inputs and reported 58 modelos, 146 revisions, and 1,402 legal references.
- Final bounded CLI review confirmed catalogue-wide grounding remains separate from selected-context filing eligibility. The five-reference historical grounding and corrupted-quotation detector independently passed: 1 passed in 7.05 seconds.
- Final handoff verification: the installed CLI/MCP suite passed nine cases and exposed one launch-fixture omission. After supplying the required installed CLI executable path in the isolated test environment, every failed-case assertion passed against the same freshly built cohort, including the real handshake and clean exit. The full suite was not rerun after this test-only fix.
- The installed Modelo 303 probe passed snapshot copying/sharing, empty-ledger aggregation, exact Decimal round-trip through 57 published 2026 export fields, and malformed-amount refusal. This proves the export-codec boundary, not a complete approved filing export.
- The outcome reference records final-generation performance, distinguishes held-authority queries from public-entry-point queries, and identifies which generation each compilation and installed proof exercised.
- Ruff and basedpyright checks for the final diagnostic boundary files: passed as reported by the implementing coordinator.
- The explicit diagnostic integration detector passed after the Modelo 200 vector pin was refreshed to generated manifest `398e70427c849ea52dff428d6e60911a1fda1383ee1467bced0abbbee7c31325`: 1 passed in 37.27 seconds.
- The paired fail-closed generated-provenance drift regression: 1 passed.

## Recommendations

No high or critical authority-backend finding remains open. Preserve the detector tests for final receipt adjacency, distinct v5 identities, evidence cache content identity, Windows artifact ChangeTime admission, sidecar input closure, content-addressed TOML fingerprints, and the structural-versus-validated type boundary.
