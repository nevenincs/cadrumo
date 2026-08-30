---
tags:
  - '#audit'
  - '#registry-relation-and-export-integrity'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:eadc54e61241105dbe2c311d0710b24d9ebea519074cb738f228ffee1d6c3216'
related: []
---

# `registry-relation-and-export-integrity` audit: `The pre-write export completeness gate can be deleted and no test reds`

## Finding

`assert_export_mirrors_manifest` — the pre-write completeness assertion that
stands between a thin draft and a written fichero — can be replaced with a no-op
and **no test in any suite that reaches the export path fails.**

The gate's *input* is tested. Its *invocation* is not. Deleting the call site is
invisible to the suite.

## Proof

Method: a pytest plugin held **outside the repository** rebinds
`cadrumo.application.filing._export.assert_export_mirrors_manifest` to a no-op in
`pytest_configure`, so nothing under `src/` is modified — a peer sweep cannot
commit the mutation and a crashed run leaves no residue. `git status` on the
package was empty throughout.

Every suite that reaches `export_draft` was run neutered, and each result
compared against a clean control:

| suite | neutered | clean control | delta |
|---|---|---|---|
| `application/filing/tests` (whole directory) | 34 failed, 525 passed, 38 deselected | 34 failed, 525 passed, 38 deselected | **none** — failure sets verified identical |
| `application/registry/tests/test_filing_export_coverage.py` + `dev/registry/tests/test_filing_emitted_byte_acceptance.py` | 10 passed, 3 deselected | — (passing under neutering is itself the proof) | **none** |
| `dev/registry/conformance/tests/test_real_closure_outcomes.py` | 2 failed, 5 passed | 2 failed, 5 passed, same two names and signatures | **none** |

The conformance suite's two failures are pre-existing and unrelated: an
`AttributeError` on `LiveFilingExportProofAuthority`, and a pydantic
`extra_forbidden` where `temporal_coverage` carries `status` / `failure_code` /
`failure_detail` / `refused_coordinates` that `RegistryClosureRevisionReport` does
not declare. Both reproduce with the gate intact.

Consistent with this, `assert_export_mirrors_manifest` appears in **no test file
at all** — only in `_export.py`, `_export_parity.py` and
`_validate_export_exemption.py`.

## What is NOT wrong — the enforcement is live and half of it is well covered

An earlier reading of this area over-claimed and is corrected here. The mandate is
**not** unenforced:

- The gate runs, and runs early. `_export.py` calls it during preparation;
  `_write_prepared_export` → `atomic_write_bytes` is a separate later call, so the
  assertion genuinely precedes any byte written.
- Its condition, `if prepared.subview.completeness_manifest is not None`, is
  correct by construction. Of 49 loadable revisions, 47 carry a manifest. The two
  that do not are both Modelo 165, which has **zero formulas** and only manual and
  informational casillas — no calculation-result casilla exists for the gate to
  check, so a manifest there would be vacuous.
- The **registry-build** half is live and well covered.
  `_validate_export_exemption.py` exists specifically to harden this gate, closing
  a hole where exemption-by-absence could suppress it: *"a casilla that SHOULD
  reach a box but was never given an export field was exempt from the very gate
  that exists to catch it — and read identically to one AEAT never prints."* It is
  exercised by `test_export_exemption_declared.py`,
  `test_export_layout_record_coverage.py` and `test_export_layout_join_ratchet.py`.

So coverage did not vanish; it **moved packages**. The commit that removed 18
export test files from `application/filing/tests` (adding 6, all M303-specific)
predates this campaign, and the replacement enforcement lives under
`domain/calculations/registry/`. Reading that commit's deletions in isolation
invites the wrong conclusion.

## What is uncovered, precisely

The gate's required set **is** tested — `test_manifest_classification.py::
test_gate_required_set_equals_computed_plus_schema_required` asserts it equals
computed plus schema-required. (That test is itself currently red for
`[200-2025-0A-on6]` with a `RegistryValidationError`; pre-existing, and not
addressed here.)

What no test asserts is that the gate is **called on the export path**. The
composition — required set, correct; assertion, present; invocation, unpinned — is
the gap.

## Direction

The gate exists to stop a structurally thin file behind a valid digest: casillas
that are calculation results or schema-required, that the manifest lists and the
record can represent, going to disk blank. A blank required casilla is
**under-declaration**, and the digest does not detect it because a digest is a
byte-integrity lock, not a completeness claim.

Today the gate works, so nothing is mis-declared. The exposure is to change: a
refactor that drops or short-circuits the call would ship green. That is the same
shape as an unproven gate — the difference between a gate that holds and a gate
that is *known* to hold.

## Remediation — owner's decision, not taken here

A test that drives `export_draft` over a draft with a blank formula-declaring
casilla and asserts `FilingExportError`, naming the missing casilla. Per the
standing rule that a gate is unproven until it bites, it must be verified by
breaking the production path deliberately — the plugin technique above does this
without touching a tracked file and is the cheap reusable form.

A secondary matter for the same owner: `modelo-export-mirrors-official-structure`
closes by naming three gates — `test_export_completeness_gate.py`,
`test_export_completeness_sets.py`, `test_fichero_boe_completeness_parity.py`.
**None exists**; all three were deleted in the commit noted above. Every gate cited
by the other ten project rules resolves, so this is a single stale citation block,
not general drift. A rule naming a gate that is not there is a dangling reference
for every future reader.

No production code, registry data or test was changed by this audit.
