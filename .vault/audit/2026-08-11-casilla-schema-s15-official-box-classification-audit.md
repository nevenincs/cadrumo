---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:dc4f81d9811361154c90db3b9c26a338f918389386031525991532b0e022b5e4'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-canonical-derivations-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S15 official box classification`

## Scope

Reviewed W02.P05.S15 against the accepted canonical-derivations decision, campaign plan, research, and repository quality constraints. Scope was limited to `_export.py`, the registry facade, and `test_official_box_classification.py`. The required contract is one facade-exported `classify_official_boxes` authority composing binding-derived fixed-width layouts, direct and repeated-row casilla addresses, explicitly reviewed binding-field representation, official XML dictionaries with source authority, and an explicit undefined state for revisions without an official layout.

## Findings

### derive-before-scan-gate | medium | Initial M720 regression consumed an already-derived snapshot

The initial M720 test selected `bundled_authority().snapshot(...).revision`. Snapshot construction already runs `derive_export_layouts_from_bindings`, so all 43 M720 binding fields were present before the classifier was called. An external mutation replacing the classifier's derive call with `revision.export_layouts` therefore left that test green. Production was correct, but the named regression did not make S15's explicit derive-before-scan step load-bearing.

### derive-before-scan-gate | resolved | Real pre-snapshot M720 revision makes derivation load-bearing

The corrected test selects the real validated authoring revision through `authority.validate_modelo("720")` and proves every declared export record initially has no fields. `classify_official_boxes` must now derive the binding fields itself to classify the two reviewed M720 declaration casillas as represented via binding. An independent runtime mutation replacing only the classifier's derive call with raw layouts made the exact test fail; restoration made it pass. No production correction was required.

No open findings.

The classifier derives layouts once before measuring any channel. Fixed-width direct fields and repeated-row mappings delegate to `fixed_width_record_casilla_ids`; binding representation requires both a resolved binding field and the explicit `FILED_VIA_BINDING_FIELD` review stamp; XML dictionary identities delegate to `xml_dictionary_entries`, which refuses absent source root, absent source catalogue, a missing dictionary source reference, and an empty dictionary; all other declared casillas become `UNDEFINED`. A real corpus probe found the only two `FILED_VIA_BINDING_FIELD` declarations are the named M720 declaration casillas.

The M100 2024 regression proves missing XML authority refuses and the real official dictionary addresses casilla `0001` while a non-addressed family identity remains undefined. The M349 regression proves the binding-derived repeated-row design addresses both a declaration total and an operator row identity even though the selected row casilla carries no `export_refs`. The M130 regression proves a nonempty layoutless revision is entirely undefined. The facade identity test imports the production owner directly.

Exact symbol inspection found one production classifier definition, one owner export, one facade import, and one facade export. No compatibility alias, secondary union, duplicate classifier, fake, stub, mock, patch, monkeypatch, skip, expected-failure marker, or mirrored dictionary/layout traversal exists on the scoped test surface.

## Verification

- Fresh semantic discovery located the classifier, canonical derivation decision, and real-registry gates before exact inspection.
- Focused S15 tests: 5 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Facade identity: the registry export is the `_export.py` function object.
- Duplicate-authority sweep: one `classify_official_boxes` definition and no assignment alias.
- Real channel census: M720 has 2 represented-via-binding and 5 undefined casillas; M349 has 13 addressed casillas; M100 2024 has 2,062 addressed and 31 undefined casillas; M130 has 20 undefined casillas.
- Corrected derive-before-scan bite: bypassing only classifier derivation made the exact M720 test red; restoration made it green.
- Prohibited test-construct scan: no hits.

## Recommendations

No further corrective action is required for S15. Preserve the corrected pre-snapshot M720 fixture so future classifier changes cannot rely on snapshot-side derivation.

Final verdict: **PASS.** The review-time gate gap is resolved. W02.P05.S15 now supplies one public three-state classifier, composes each official representation channel through its canonical authority, refuses ungrounded XML evidence, and has real regressions that make derive-before-scan, direct/row addressing, reviewed binding representation, and layoutless undefined behavior observable.
