---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:35470bd0f55b611c3807cd0612a36f555ecfd605f1fcde0edef98cf3af457577'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S05 completeness manifest authoring shape review`

## Scope

Formal read-only review of the unstaged `W01.P02.S05` registry-data relocation and `test_completeness_manifest_authoring_shape.py` against the full `casilla-schema` plan and research, the registry loader's fragmented-section merge contract, registry-authority and quality rules, and shared-worktree safety. Semantic discovery used `vaultspec-rag` before exact inspection. The review independently checked source-to-destination blob identity, loaded completeness-manifest ownership, canonical anchor placement, Modelo 100 continuation placement, legacy-layout removal, loader behavior, the real registry verifier, test construction, and the scoped shared-worktree boundary.

The change is mechanical. Every former root `completeness-manifest.toml`, legacy `completeness/` fragment, and hyphenated anchor maps to the canonical `completeness_manifest/0001-completeness_manifest.toml` anchor or, for Modelo 100 continuation fragments, to the same `completeness_manifest/` directory. A Git-object census found 57 deleted source blobs and 57 untracked destination blobs, with a one-to-one path mapping and zero content-hash mismatches, missing destinations, or extra destinations.

The loaded and authored populations agree by property rather than by a pinned tally: every revision whose production-loaded model has a completeness manifest has the canonical anchor, and every canonical anchor belongs to such a loaded revision. The reviewer observed 56 on each side only as diagnostic evidence. The four previously present legacy forms are absent. Modelo 100 continuation fragments remain byte-identical and now share the canonical directory with their anchor.

## Findings

No actionable findings.

The new test is a structural cross-check between two independent observations: the real production loader identifies revisions that semantically carry a completeness manifest, while a direct bundled-tree glob identifies revisions that physically carry the canonical anchor. Equality is asserted between those derived sets; no exact corpus count, modelo allowlist, mirrored TOML merge, or copied business rule is encoded. Separate negative assertions reject the known root-file, `completeness/`, hyphenated-anchor, and generic-manifest legacy layouts. The test imports the real loader through the existing registry test support and uses the real bundled resource path. It introduces no fake, mock, stub, patch, monkeypatch, skip, xfail, or compatibility read path.

The loader itself is unchanged. Its existing singleton-table merge appends completeness-manifest `casillas` across fragments, and the real bundled registry compiles and validates after relocation. No peer-owned ledger, quality, or unrelated audit WIP was included in the S05 surface.

## Recommendations

No changes requested. Keep future completeness-manifest authoring under the canonical `completeness_manifest/` section directory, retain `0001-completeness_manifest.toml` as the mandatory anchor, and keep any large-manifest continuation fragments beside that anchor. Do not add loader tolerance or compatibility aliases for the removed layouts.

## Verification

- Exact Git-object relocation proof: 57 deleted sources, 57 new destinations, zero missing destinations, zero extra destinations, and zero blob-id mismatches.
- Production-loader/filesystem census: 56 loaded manifest revisions and 56 canonical anchors; zero missing anchors and zero orphan anchors.
- Legacy-layout census: zero root `completeness-manifest.toml` files, zero `completeness/*.toml` files, zero hyphenated canonical-directory anchors, and zero generic `0001-manifest.toml` anchors.
- Focused authoring-shape test: 1 passed in 3.04 seconds.
- Existing real completeness-fragment loader test: 1 passed in 0.29 seconds.
- Real `aeat app registry verify`: verified true with 73 modelos, 94 revisions, 799 legal references, 316 source references, and 16,800 casillas.
- Scoped Ruff: exit 0, all checks passed.
- Scoped BasedPyright: exit 0, zero errors, warnings, and notes.
- Scoped `git diff --check`: exit 0; relocated TOML destinations are byte-identical to their tracked source blobs.
- Prohibited-test-construct scan: no fake, stub, mock, patch, monkeypatch, skip, or xfail construct in the new test.

Verdict: **PASS.** `W01.P02.S05` establishes the single canonical completeness-manifest authoring shape without changing registry semantics, losing or altering a moved blob, hard-coding the corpus population, restoring compatibility, or absorbing unrelated shared-worktree changes. The production loader and full registry verifier remain green.
## Independent-review addendum

### s05-completeness-manifest-shape-review | medium | The gate denies known legacy paths but does not enforce the canonical directory for every continuation fragment

The loader recursively discovers every TOML file below a revision and routes fields by TOML content, not by the fragment's parent-directory name. The new test proves that each loaded manifest revision has the exact canonical anchor and bans four historical layouts, but it never inspects the location of every fragment that declares `completeness_manifest`. Consequently, a revision can retain its canonical anchor, move a completeness-manifest continuation into any novel sibling directory, and still pass this test and the production loader. That is an enumerated denylist of known old shapes, not the plan's property that exactly one authoring shape exists. The current Modelo 100 continuations are correctly placed and byte-identical; the finding concerns the durability and truthfulness of the new shape gate.

## Revised recommendation

Strengthen the test without a hard count or modelo allowlist: inspect every bundled revision fragment that semantically declares `completeness_manifest` and require its revision-relative path to be below `completeness_manifest/`; continue requiring the exact `0001-completeness_manifest.toml` anchor for every production-loaded manifest. Use the standard TOML reader or stdlib TOML parsing for structural identification rather than mirroring loader merge behavior. Preserve all relocated bytes.

Revised verdict: **CHANGES REQUESTED.** The 57-file relocation is complete, byte-identical, and registry-valid, but `W01.P02.S05` cannot yet claim a durable single authoring shape because its new gate accepts completeness-manifest continuations in arbitrary noncanonical directories.
## Finding resolution

The MEDIUM shape-gate finding is resolved. The test now parses every TOML fragment below every bundled revision that contains the `completeness_manifest` field, identifies the semantic field structurally, and requires the fragment's parent to equal that revision's exact `completeness_manifest/` directory. The enumerated four-path denylist is gone. Exact canonical-anchor equality against the production-loaded manifest population remains, and no hard corpus count or modelo allowlist was introduced.

An independent temporary-tree bite probe created a valid canonical anchor plus a completeness-manifest continuation under a novel sibling `novel_shape/` directory. The strengthened helper found both semantic fragments and classified exactly the novel continuation as misplaced. This exercises the loader-permitted counterexample that caused the finding and confirms the repaired property fails it.

Resolution verification:

- Novel sibling-directory bite probe: two semantic fragments found, one misplaced continuation detected, exact expected offender true.
- Focused authoring-shape test: 1 passed in 7.19 seconds.
- Scoped Ruff: exit 0, all checks passed.
- Scoped BasedPyright: exit 0, zero errors, warnings, and notes.
- Scoped `git diff --check`: exit 0.
- Relocation recheck: all 57 source-to-destination Git blob pairs remain byte-identical; zero mismatches.

Final verdict: **PASS.** The sole finding is closed. `W01.P02.S05` now carries a property-based, count-free gate that requires the canonical anchor for every production-loaded manifest and rejects every semantically identified completeness-manifest fragment outside the canonical directory, including previously unknown path shapes. The byte-identical data relocation and real registry semantics remain unchanged.
