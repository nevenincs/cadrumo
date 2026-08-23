---
tags:
  - '#audit'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:fb9c3a71834a6ebb78b15b17a955f6dc0870c30241ac2fea548aa0b7b5b626d4'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-authority-adjudication-adr]]"
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# `issue-620-external-pdf-signal` audit: `authority adjudication final review`

## Scope

Fresh-context review of the three-axis external-PDF authority contract, all ten
adjudicated sidecars, and the registry-aware parser outcome matrix against the
accepted authority-adjudication ADR.

## Findings

### official-source-evidence-lock | medium | Valid-looking authority evidence can drift without failing the focused contract gate

`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:79` through
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:100` validates
only the authority token, HTTPS host, digest shape, and uniqueness of candidate
page numbers.  The coverage check at
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:221` through
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:225` likewise
does not bind the reviewed document id, URL, digest, or official page numbers.
The focused mutations at
`src/cadrumo/tests/fixtures/external_layout_candidates/tests/test_candidate_contract.py:182`
through
`src/cadrumo/tests/fixtures/external_layout_candidates/tests/test_candidate_contract.py:224`
therefore reject malformed evidence but accept any syntactically valid digest
and any positive official-page selection on an allowed host.  The ten current
sidecars carry the reviewed four authority digests and correct page mappings,
but a later edit can replace those facts with valid-looking values while the
gate remains green, contrary to the ADR requirement that contract tests validate
the official-source evidence.

Resolved in S16. The contract now compares the complete authority,
`document_id`, official URL, SHA-256, and ordered candidate-to-official page
mapping against a committed per-modelo evidence coordinate. Focused mutations
prove that well-formed substitutions of every coordinate component, including
a host-valid alternate authority pair and a complete but wrong page mapping,
fail validation.

Independent re-review of commit `696c0bf3e8` confirms the resolution. The
complete coordinate is enforced for every allowed modelo before a candidate can
load, and the focused gate exercises each valid-looking substitution rather
than only malformed values. Final status: resolved; no remaining actionable
official-source evidence-lock finding.

### counterpart-digest-binding | medium | Pair-render evidence is not bound to the physical opposite candidate

`ExternalLayoutPairRenderEvidence.counterpart_sha256` at
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:103` through
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:109` is only a
64-hex string.  Candidate validation at
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:226` through
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:229` checks the
opposite kind but never loads that sidecar or compares its physical content
digest, while `physical_candidate_mismatches` at
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:336` through
`src/cadrumo/tests/fixtures/external_layout_candidates/__init__.py:349` checks
only the candidate's own bytes.  All five committed pairs are currently
reciprocal and correct, but substituting any other valid digest would not fail
the focused suite, so the claimed digest-bound render relationship is not yet a
gate-enforced contract.

Resolved in S16. The physical gate now hashes the actual adjacent opposite-kind
PDF selected by `counterpart_kind` and compares that observation with the
declared `counterpart_sha256`. A focused mutation retains a syntactically valid
64-hex digest while replacing its value and proves that the gate reports a
counterpart content mismatch.

Independent re-review of commit `696c0bf3e8` confirms the resolution. Opposite
kind is still schema-bound, and every canonical sidecar reaches the physical
counterpart hash comparison through the parametrized corpus gate. The focused
valid-wrong-digest mutation bites, and the complete contract module passes 40
tests. Final status: resolved; no remaining actionable counterpart-digest
finding.

### parser-registry-review | low | no actionable findings

The matrix binds M130 and M131 to their current authored revisions and M303 to
historical revision `2025`; a direct registry probe confirms that the 2025 M303
snapshot excludes casilla 112 while `2026-y-siguientes` includes it. M036 and
M349 use the separately typed and labelled out-of-revision parser path, and the
applicability assertion requires both sidecars to refuse an authored revision.
All ten identities retain exact missing, malformed, ambiguous, and empty-value
buckets, so fabricated values or a changed support classification fail the
matrix. The focused candidate-contract, matrix, and M130 boundary modules pass
59 tests.

## Recommendations

Final status: both MEDIUM findings are resolved and independently re-reviewed.
No open actionable finding remains at any severity. No live-network dependency
or additional official PDF bytes were introduced, and the closing focused gate
passes all 63 authority-contract and parser tests.
