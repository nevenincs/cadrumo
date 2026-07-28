---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S50'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace conformance-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S50 and 2026-07-27-conformance-cli-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The eliminate the monkeypatch machinery from the burned-version ledger tests and the registry snapshot freshness tests without weakening what either test proves, honouring the recorded trap that a threaded authority parameter lets a naive cache key stop colliding so the behavioural test passes with the defect present and ## Scope

- `src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# eliminate the monkeypatch machinery from the burned-version ledger tests and the registry snapshot freshness tests without weakening what either test proves, honouring the recorded trap that a threaded authority parameter lets a naive cache key stop colliding so the behavioural test passes with the defect present

## Scope

- `src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Split the burned-version ledger reader into `read_ledger(path)`, a pure function of the file it is handed, and reduce `burned_versions()` to the cached accessor that calls it with the shipped ledger constant.
- Rewrite the six ledger test sites to hand `read_ledger` a real temporary file instead of re-pointing the module-level ledger constant, dropping the three `monkeypatch.setattr` calls, the three fixture arguments, the three type references, and the six process-wide cache resets they needed.
- Add a control asserting the shipped accessor is that same reader over the shipped ledger, so the refusal cases keep guarding the shipped path rather than a function beside it.
- Add a well-formed-ledger control, so the seven refusal cases can distinguish a precise refusal from a reader that rejects everything.
- Replace the registry snapshot freshness behavioural proof with a cache-eviction proof against the real process authority, removing the two synthetic resource-registry slot dataclasses, the two full bundled-registry tree copies, and all three `monkeypatch.setattr` calls on the private resources alias.
- Drop the substitution from the law-determined resolution test, which copied and re-validated an unmodified registry tree and compared it against itself.
- Record at the site why the eviction shape is immune to the threaded-authority trap, and cross-reference the registry layer test that already owns the tree-change contract.

## Outcome

Both modules are free of monkeypatch machinery, and the inventory gate is green because the constructs are gone rather than hidden: measured against the pre-change content through the gate's own detector, the ledger module carried twelve violations and the freshness module ten, and both now report zero. Neither file was added to an allowlist, a ratchet, or a baseline, and no hand-rolled save/restore replaced either construct.

The ledger change is dependency injection at the reader boundary. Which ledger to parse is the caller's decision, so the malformed-shape refusals are now exercised against real files on disk. A side effect worth naming: the previous tests cleared a process-wide cache four times per case to force a re-read, which the new shape no longer needs.

The freshness change is the harder half, and the recorded trap is real. A memo above the filing resolver is invisible while the authority's own snapshot cache is warm, because both layers hand back the same object; it becomes visible the instant the layer below is invalidated, because a memo-free resolution rebuilds the snapshot while a memoized one returns the object it pinned. The test therefore resolves once, evicts exactly that entry from the authority's cache, and resolves again, asserting the second result is a rebuilt object. Both resolutions carry byte-identical arguments and reach one authority instance, so nothing varies that a memo could key on, which is precisely why the trap does not apply: the trap depends on the test varying a value a naive cache key could absorb. Evicting a cache entry is invalidation of real state, not substitution of a collaborator, and nothing is re-pointed, replaced, or restored.

Four facts were confirmed by measurement before the test was written, not assumed. The filing resolver reaches the same authority instance the process resource registry exposes. Two successive resolutions with a warm authority cache return the same object, so object identity is a meaningful signal. Evicting the entry makes the next resolution build a new object. And a real registry-tree edit under one root is observed through the production repository reset. The fourth fact is the tree-change contract, and it is already proven at the layer that owns it, against a minimal synthetic tree, so re-proving it here was dropped rather than duplicated. That is where the runtime saving comes from: the module previously copied and re-validated the whole bundled registry tree three times.

Defect reintroduction proves the migrated test still catches what it was written for. Two defect shapes were injected into the filing resolver in turn and then reverted.

The first was the shape the structural companion cannot see, a hand-rolled module-level dict memo keyed on modelo and period:

```
FAILED src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py::test_snapshot_resolution_is_not_memoized_above_the_authority
1 failed, 2 passed in 13.40s
```

with the assertion text

```
AssertionError: registry snapshot resolution returned the snapshot it had resolved before the
authority's cache entry was evicted: a cache above the loader is keyed without the
registry-tree fingerprint, so it outlives the authority that owns invalidation and a filing
would be computed under a superseded revision's norms
```

That run is the sharpest evidence in this Step: the structural companion test PASSED with the defect present, so the behavioural test is the one doing the work, and replacing it with a structural check alone would have been the silent weakening this Step exists to avoid.

The second was the classic functools cache wrapper, caught by both tests:

```
FAILED src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py::test_snapshot_resolution_is_not_memoized_above_the_authority
FAILED src/cadrumo/application/filing/tests/test_registry_snapshot_freshness.py::test_snapshot_resolution_exposes_no_cache_handle
2 failed, 1 passed in 14.74s
```

The ledger tests were proved the same way. Tolerating a duplicate version and reading an absent ledger as an empty set were injected together and both refused to pass:

```
FAILED dev/release/tests/test_burned_versions.py::test_a_duplicated_version_refuses
FAILED dev/release/tests/test_burned_versions.py::test_an_absent_ledger_refuses_rather_than_reading_empty
2 failed, 14 passed in 2.89s
```

Clean runs after every probe was reverted: the freshness module reports `3 passed in 13.16s` against `3 passed in 328.98s` for the pre-change module at the same test count, the whole filing suite `258 passed in 69.48s`, the release suite `194 passed in 31.30s`, and the inventory gate `1 passed` on the no-monkeypatch check. The type checker is silent, and lint and format are clean on all three files.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

The defect-reintroduction proof required temporary edits to a production module in the filing package. A peer campaign's uncommitted work appeared in that same module part-way through the Step, splitting an export-parity helper into a new module. Each probe was applied and reverted by exact-string rewrite rather than by any git operation, the peer's change is intact at the end of the Step, and only the two test modules and the ledger reader are staged. Nothing under the export path was touched.

The behavioural proof reaches one private attribute: the authority's snapshot cache. There is no public equivalent, and this was confirmed rather than assumed. The public reset drops the repository's authority reference, but the authority load is keyed on the registry-tree fingerprint, so an unchanged tree returns the same instance with its snapshot cache still warm, which is semantically correct and therefore cannot discriminate. Exposing a public clear method instead was rejected: it would have no production caller, which is the test-hook setter shape the override-seam gate exists to prevent. The eviction is written against the cached value rather than a reconstructed key, so it stays correct if the cache key gains a dimension, and if it matches nothing the next assertion fails loudly rather than reporting a green on an eviction that never happened.

Three routes were considered and rejected before this one, and the reasoning is recorded in the module docstring so the next reader meets it at the site. A hand-rolled save and restore on the same private target hides the construct from the gate's matcher rather than removing it. A scoped resources override is the exact shape the override-seam gate forbids with no allowlist and no baseline. Threading an authority parameter is the trap: it lets a naive cache key absorb the varying value, so the two-authority setup stops colliding and the behavioural test passes with the defect present.
