---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:52f9bdb6132be846dc793d423b3b0db5f6397f38d678725edde247f6f1d8969e'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `S23 concurrency staleness review`

## Scope

Reviewed the S23 manifest relaxation and its focused tests against the approved plan step,
execution record, accepted declustering ADR, and the current manifest, graph, rehearsal,
receipt, and replay contracts. The review tested whether unrelated global inventory churn is
tolerated without weakening current selected-finding identity, locator/path binding, target
occupancy, complete exact byte preconditions, graph reference containment, manifest identity,
or receipt replay freshness. No implementation or test code was modified.

## Findings

### downstream-global-digest-refusal | high | The relaxation does not survive rehearsal or replay

`validate_object_name_manifest` now correctly tolerates a manifest inventory digest that
differs from the current inventory while revalidating each selected operation locally.
However, `rehearse_object_name_component` still requires the copied current inventory digest
to equal both the supplied current inventory and `manifest.inventory_digest`, and records the
receipt inventory digest from the manifest. Replay likewise requires the receipt inventory
digest to equal both current inventory and manifest. Unrelated inventory churn therefore
passes S23's validator but is refused at the next mandatory workflow phase. The approved step
objective--preventing unrelated churn from invalidating a leaf operation--is not achieved.

### end-to-end-churn-teeth | medium | The new test proves only validator tolerance

The amended test replaces the manifest digest and asserts direct validator success, then
retains strong negative cases for selected finding identity and locator. It does not pass that
same stale-global/current-local manifest through canonical component derivation, rehearsal,
receipt generation, and replay preflight. Consequently it remains green while the production
workflow still rejects the exact concurrency case S23 exists to permit.

No safety regression was found in the validator relaxation itself. Current enforced finding
identity must still exist; the old locator must remain a qualified site and resolve to the
same object kind and path; the proposed target name and module path remain globally
unoccupied; every existing changed path remains exhaustively preconditioned; source and
affected bytes are rehashed exactly; link-like paths are refused; and current graph discovery
still exposes undeclared reference surfaces. The manifest digest continues to bind the
authored inventory value as immutable reviewed input rather than treating it as current-state
authority.

## Recommendations

Carry the S23 distinction through receipt generation and replay: rehearsal should require the
copied inventory to equal the supplied current inventory, record that current digest in the
receipt, and leave the possibly older authored inventory value bound only through the exact
manifest digest. Replay should require receipt inventory to equal the freshly scanned current
inventory and require the exact manifest digest, without also equating current inventory to
the manifest's historical census value. Preserve every operation-local and graph check.

Add an end-to-end detector-tooth fixture that introduces an unrelated declaration after
manifest authoring while preserving the selected finding, locator, target availability, and
all declared bytes. It must validate, derive the same leaf component, rehearse successfully,
bind the new current inventory in the receipt, and replay only while that current receipt and
all local bytes remain unchanged. Pair it with selected-finding, new-target-collision,
new-reference-edge, and selected-byte drift refusals.

## Validation

The focused manifest suite passed 42 tests in 2.91 seconds. Ruff, Ruff-format, ty, and byte
compilation checks passed. Final review status is one high and one medium finding, with no
critical or low findings.

## S24 resolution status

Resolved: `downstream-global-digest-refusal` is closed by separating authored manifest
identity from current inventory evidence. Rehearsal now binds the exact manifest digest,
records the inventory digest scanned from its verified disposable copy, and limits receipt
baseline identity to declared input and changed paths. Replay requires the exact manifest
digest and exact guarded baseline, regenerates transformation, findings, tools, generators,
and gates from current state, and no longer equates the historical manifest inventory value
with the current receipt inventory.

An independent disposable end-to-end probe added a singular unrelated Python declaration
after manifest authoring. Its inventory digest differed from the manifest, rehearsal recorded
that new current digest, replay changed only the selected declaration, and the unrelated file
remained byte-identical. Selected finding/site/path checks, target occupancy, exact guarded
bytes, graph reference containment, output and gate equality, and transactional rollback
remain fail-closed.

Open: `end-to-end-churn-teeth` remains medium because the committed success test mutates an
unrelated `.txt` file and reuses the pre-churn inventory object. It proves scoped byte
tolerance, but not the S23 condition of a real unrelated Python declaration changing the
inventory digest across manifest, receipt, and replay.

## Final remediation re-review

The committed replay detector now creates `dev/concurrent_helper.py` with the distinct
singular declaration `helper_runtime`; the focused test passes and proves that the new Python
file is preserved while the selected declaration is replayed. This improves the fixture from
plain byte churn to a real source-census mutation.

Open: `end-to-end-churn-teeth` remains medium. The test continues to call
`replay_object_name_component` with the pre-mutation `inventory` and pre-mutation `component`
returned by `_case`; it neither rescans after creating `concurrent_helper.py` nor asserts that
the current inventory digest differs from the receipt or manifest digest. Therefore it would
remain green if replay rejected a freshly supplied post-churn inventory, which is the path the
real CLI exercises. The production behavior remains supported by the earlier independent
fresh-inventory probe, so this is a committed regression-test gap rather than a demonstrated
implementation defect.

Focused validation passed both the Python-churn replay case and the hash-time disappearance
case (2 tests), and Ruff lint, Ruff format, and ty all passed for the four affected
implementation/test files. Final status remains one medium finding and no critical, high, or
low findings.
