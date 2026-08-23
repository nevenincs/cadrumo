---
tags:
  - '#audit'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:09b19b379d922f2b67a1c43850320aa5a5d09e34bbac52480be86f6e01685db9'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---

# `issue-620-external-pdf-signal` audit: `inventory review`

## Scope

Fresh-context review of the accepted plan, ADR, research, S01-S09 execution
records, and the issue-620 paths carried by commits `498919042b`,
`7bb43832e7`, `6ed0bfeba8`, `fa85cabebc`, `3b0ab08d7e`, `5573854466`,
`c98f334880`, `278353387c`, `a115912027`, `a8e60ec9b4`, and `baeda28d7d`.

The review covered all ten candidate PDF/sidecar pairs, their content addresses
and physical observations, the strict external-source contract, the M130
printed-box anti-vacuity regression, the five-modelo outcome matrix, the M130
profile evidence correction, the provisional parser stamp, the reconciliation
advisory, and lifecycle consistency. All ten committed PDFs were independently
confirmed tracked and byte-equal to their declared SHA-256 and size. The exact
92 focused tests passed sequentially, but that green result currently includes
the false M036 expectation recorded below.

## Findings

### m036-invalid-period | high | The matrix manufactures unavailability instead of exercising either M036 PDF

Both M036 cases in `test_external_layout_candidate_matrix.py` select period
`01`. The authoritative M036 revision accepts only the event periods `alta`,
`modificacion`, and `baja`, so `01` necessarily raises
`NoRevisionForPeriodError`. The helper catches the broad
`RegistrySnapshotError` base and reports `unavailable_registry_snapshot`, making
the two tests green without loading or classifying either candidate PDF. A
direct measurement through the same production primitives with the valid
period `alta` reaches both PDFs and returns `blank_no_values`, with exactly
`decl.event-kind` missing and no values, malformed targets, or ambiguous
targets. This is a false signal in the central S08 acceptance matrix and leaves
the feature with an unresolved high-severity correctness finding.

### inventory-orphan-files | medium | The exact-inventory gate ignores unpaired or surprise PDF bytes

The candidate contract constructs its inventory exclusively from `*/*.json`
sidecars. It proves that each discovered sidecar has a matching readable PDF,
but it does not prove the converse and does not reject an extra PDF-only row,
an unexpected numeric modelo directory containing only bytes, or other surprise
candidate files. Such bytes can enter the checkout-only third-party corpus
without appearing in the claimed exact five-by-two admission matrix. The gate's
stated missing-or-surprise-row guarantee is therefore narrower than its name
and documentation.

### synthetic-corpus-terminology | low | Some gate comments still describe synthetic fixtures as real

The M130 evidence correction updates the principal test names and docstrings,
but `test_corpus_round_trip_gate.py` and
`test_provisional_specimen_gate.py` retain several comments or paragraphs that
call the committed `justificantes` tree a "real fixture tree", "real fixture
inventory", or say that all real modelos carry real fixtures. Those statements
conflict with the corrected evidence boundary and can mislead later authors,
although they do not change runtime behavior.

## Recommendations

- Resolve `m036-invalid-period` before feature completion: use an authoritative
  M036 event period such as `alta`, assert the measured `blank_no_values`
  outcome for both variants with exactly `decl.event-kind` missing, and avoid
  converting an arbitrary registry snapshot failure into an expected
  unavailability result.
- Resolve `inventory-orphan-files` by asserting the complete physical candidate
  topology: exactly the expected numeric modelo directories and exactly one
  same-stem JSON/PDF pair for each `plain` and `fillable` identity, with no
  orphan or surprise candidate files.
- Resolve `synthetic-corpus-terminology` by replacing the remaining "real"
  descriptions with "committed synthetic" wording while preserving references
  to genuinely external or authenticated evidence.
