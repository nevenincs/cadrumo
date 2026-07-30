---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S35'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# derive the embedded core-type set for the compiled cache key from the compiled models annotations rather than a remembered hand list, or assert the derived set is a subset of the list, covering the ten unenrolled types including the core Modelo enum

## Scope

- `src/cadrumo/domain/calculations/registry/_compiled_cache.py`

## Description

- Delete the hand-maintained `_EMBEDDED_SCHEMA_CORE_SYMBOLS` tuple from the compiled-cache key.
- Derive the embedded foreign-type set by walking the compiled models' `model_fields` annotations, unwrapping type aliases, `Annotated` metadata, unions and container parameters, and yielding the enum CLASS behind every member of a `Literal` of enum members.
- Add the concrete binding-selector models to the walk roots, enumerated through the registry's own `selector_model_for_source` accessor, because `DataBindingDefinition.selector` is typed as an open `BaseModel` and hides its family model from any annotation walk.
- Hash each derived type's `module.qualname` marker plus its defining file's bytes, deduplicated per file and keyed on the path relative to the package root so the fingerprint does not move with the checkout location.
- Pin the in/out boundary as named package-root constants and expose `roots` as an injectable parameter on both the derivation and the fingerprint so detection power can be proved rather than restated.
- Replace the two hand-list guard tests with derived-set equivalents, and add five: the package-root pin, the injected-new-type detection proof, its no-foreign-type control, the `Literal` hole, the polymorphic-selector hole, and an object-graph walk of the real compiled payload asserting nothing it embeds escapes the key.

## Outcome

The finding reproduced exactly. The hand list carried five entries; an object-graph walk of the real compiled bundled payload observes twenty-one first-party types reconstructed from outside the registry package, so sixteen were unhashed — including the core `Modelo` enum and the whole IVA family (`IvaCategory`, `IvaRateKind`, `EUMemberState`, `IvaCashAccountingTreatment`, `IvaFlowDirection`, `OssIossRegime`, `InvoiceKind`, `TransactionKind`) and `CasillaFieldKind`. The derivation now yields twenty-four types (a superset: it also covers annotation-reachable surfaces the current tree happens not to instantiate, such as `ConvenioOverrideKind` and `IvaExemptionArticle`), and the payload-walk gate confirms the observed twenty-one are a subset of it.

Two structural blind spots had to be closed for the derivation to be honest, and each is now a test that flips if it is reopened. `Modelo` was unreachable because the ledger selectors type their `modelo` field as `Literal[Modelo.M100]`: the annotation names only values while the compiled object pickles a real enum member, so a walk that skipped `Literal` reported the type absent. The IVA family was unreachable because `selector` is annotated as bare `BaseModel`, so a walk from the two schema roots alone cannot reach any concrete selector family; a test asserts `IvaCategory` and `Modelo` are absent from the schema-roots-only derivation and present in the full one.

On derived-versus-listed for the cache key, the ruling is derived, and the key-stability objection does not survive inspection. The alternative — keep the hand list and assert the derived set is a subset of it in the test — was rejected on two grounds. First, the cost it was meant to avoid is not real: the key already folds a content hash of every registry-package source file, and this Step edits one of them, so every existing cache is invalidated by this commit whichever option is taken. There is no key-stability to preserve. Second, a list plus a subset gate is two authorities for one fact, and the fact would still be authored by memory with a gate scolding the author afterwards; deriving removes the failure for every annotation-reachable type instead of making it loud. Loudness is still needed for the residual polymorphic hole, and that is what the payload-walk gate provides — but it is measured against the real compiled objects, which is ground truth, where a hand list could only ever be measured against its author's memory.

Anti-tautology proof, both directions and injection-based rather than fixture-based. `test_a_newly_embedded_foreign_type_is_derived_and_moves_the_fingerprint` first asserts `AuthProviderKind` is absent from the real derived set (the precondition, so the proof cannot go vacuous), then hands the derivation a root embedding it and asserts both that the marker appears and that `_compute_loader_code_fingerprint` returns a different digest. The old hand list could not fail this way at all: an unenrolled type simply never entered the key and no assertion anywhere flipped. The control `test_a_root_embedding_nothing_foreign_leaves_the_fingerprint_unchanged` adds a root whose fields are `str` and `int` and asserts the derived set and the fingerprint are byte-identical, so the proof above cannot be satisfied by anything that merely reacts to a root being appended. The payload-walk gate carries its own anti-vacuity floor: more than ten observed types, with `Modelo` and `IvaCategory` named explicitly, before the subset assertion runs.

Verification, actual output. The owning module: `12 passed in 61.08s`, collected 12. The registry package under four workers: `2 failed, 3079 passed, 2 warnings in 240.07s`, the two failures both in `test_loader_cache_isolation.py` (`test_bundled_root_disk_cache_is_shared_across_processes`, `test_bundled_root_disk_cache_survives_across_separate_real_pytest_sessions`) — the known peer-churn class, since a peer committed the whole working tree mid-run and was editing two registry-package sources whose bytes are in the cache key. Re-run serially on a settled tree: `11 passed in 62.70s`, so both are spurious rather than a regression. `ruff format` reports `2 files left unchanged`, `ruff check` `All checks passed!`, `ty check` `All checks passed!`. The docstring core-struct link gate and the lazy-import policy gate pass; two import-hygiene assertions fail on a sanitizer test importing `SRC_CADRUMO`, landed by a peer at HEAD and untouched by this Step.

## Notes

Semantic discovery was explicitly waived by the operator for this Step: the RAG index is broken and the service stopped, so grounding was `rg` plus whole-file reads, and the service was not started, restarted, or reindexed.

The commit contract was broken by a peer, not by this Step. While the work was under verification a peer ran an operator-directed sweep committing the entire working tree (`33129cc83f`, "chore(worktree): operator-directed commit of all in-flight work"), which carried both files of this Step — 243 changed lines in the cache module and 258 in its test — into that commit alongside thirty-three unrelated files from other campaigns. The sweep commit records that it gated on tree-wide collection at 16052 tests before landing. No separate explicit-pathspec commit for this Step therefore exists, and un-bundling it is not available: every mechanism for doing so is a forbidden destructive git operation in this shared worktree. The code is at HEAD and verified there.

A transient peer breakage was observed and correctly attributed rather than chased. Mid-session the working-tree registry package became unimportable with `NameError: name 'governance_stamp_fields' is not defined` from the revision schema. HEAD carried no reference to that symbol at all, so the break was a peer's half-landed edit in the working tree rather than a property of the tree; it resolved on its own once they finished, and nothing was touched to work around it.

The derivation is a superset of what the current tree instantiates, deliberately. Over-inclusion costs one extra hashed source file and cannot cause a stale read; under-inclusion is the hazard this Step exists to close.
