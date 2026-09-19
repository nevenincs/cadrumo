---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e6a47fd828f16dfcd17b023cf3e7f1e56925f8c750c6cc2088b7da00f8b13ca9'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `s40 allowed values`

## Scope

Verdict: **PASS. No open critical, high, medium, or low findings remain.**

Independent review of the final S40 logical diff against the accepted generator-authority ADR, plan row at the reviewed 930ef9f401 and 6f3cf8b918 snapshots, and the completed S37 and S38 execution and audit records. The review covered `ExportFieldDefinition.allowed_values`, the sole registry fixed-width codec's render and parse enforcement, the focused codec tests and structural owner guard, and only the loader-semantic key, projection, schema-version, and digest-mutation changes in the shared provenance files.

The final schema canonical-sorts the domain, refuses empty, duplicate, non-ASCII, non-digit, noncanonical, over-width, signed, non-integer, non-left-zero, non-right-justified, literal, filler, checksum, and value-policy-overlap uses. Render and parse enforce membership symmetrically after numeric normalization. Loader-semantic provenance is invariant to member order but changes for an actual member mutation. The production structural sweep finds `_require_allowed_value` only in the registry codec, and the reviewed tests use real production imports without fake, mock, stub, monkeypatch, skip, xfail, mirrored business logic, or tautological production shadow.

Before remediation, the reviewer independently collected 46 focused passes and clean Ruff and BasedPyright gates. After remediation, the executor's current-snapshot lane collected 47 selected passes, clean Ruff, and zero BasedPyright diagnostics. The reviewer independently recollected clean Ruff and zero BasedPyright diagnostics on the remediated files. Three pytest retries were prevented before collection by concurrent peer import edits, first the registry `_ids.py` Casilla export migration and then an indentation error in `domain/filing/_protocols.py`; no S40 test failed. Paused S32 work shares the development provenance files but does not invalidate the scoped S40 result, and its unrelated hunks are excluded from this verdict.

## Findings

### overlapping-domain-authorities | high | A field could combine an exact value policy with a contradictory allowed-values domain

The initial review found `ExportFieldDefinition` validating `value_policy` and `allowed_values` independently and admitting both on one unsigned integer field. A direct production-boundary probe showed a selected-1/unselected-0 field with `allowed_values=("1",)` accepting `1` while refusing policy-valid `0`, `False`, and `None`, creating two value-domain authorities and contradicting S37.

Resolution: **RESOLVED.** Schema hydration now refuses any `allowed_values` and `value_policy` coexistence. A real regression requires that overlap to fail. The domain is canonical-sorted at hydration, and provenance tests prove reorder invariance while retaining sensitivity to member changes. One semantic-domain authority now applies to each field.

## Recommendations

No S40 follow-up is required. Preserve mutual exclusion between `value_policy` and `allowed_values`, canonical member ordering, symmetric render/parse enforcement, loader-semantic mutation sensitivity, and the sole registry-codec owner guard. Re-run the same focused lane after concurrent shared-tree imports stabilize to refresh reviewer-collected pytest evidence without weakening this PASS boundary.
