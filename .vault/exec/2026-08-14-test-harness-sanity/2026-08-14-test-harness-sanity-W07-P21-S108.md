---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ea66ccbc6df3e4f0fe6291dc48fb4ffb03be09aacb9e7edc2780ae0387aa9bba'
step_id: 'S108'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---
# Adjudicate the substitutable secure-storage-root fixture pair the manifest now refuses on

## Scope

- `src/cadrumo/application/setup/tests`
- `src/cadrumo/application/wizard/tests`

## Description

- Confirm the pair is genuinely substitutable rather than merely similar, by checking what each body closes over as well as its name, body, docstring, signature, scope and autouse.
- Add the pytest adapter beside its already-canonical context manager in the shared test package, following the established provider convention.
- Rename the fixture from `_backend` to `profile_storage_root` and update all seven request sites.

## Outcome

The ownership manifest refused to generate at all — a hard exit with no manifest written — naming two `_backend` fixtures as substitutable duplicates. The adjudication is that the refusal was correct.

This pair is the genuine article, unlike the false positives that preceded it in this campaign. Every earlier cluster examined here failed on one axis: identical bodies that closed over a module-level constant holding a different value per file, so a flat merge would have unified behaviour while every test still passed. This pair closes over nothing at module level, so nothing distinguishes the two definitions.

The underlying mechanism was already canonical and already shared. Only the four-line pytest adapter over it was duplicated, so the adapter now sits beside its own mechanism rather than in a new invented home.

Measured both directions: before, the manifest exits 2 naming both sites; after, it generates cleanly at 544 fixtures with `substitutable_duplicate_count = 0`. All seven tests across the two modules pass.

## Notes

The fixture is renamed rather than only rehomed. `_backend` names an implementation detail and says nothing about what the fixture yields, so a search for the concept "storage root" could never have found it — the same reason the duplicate survived unnoticed in the first place.

The consumers re-export the imported fixture through `__all__` rather than carrying a blanket suppression comment. A fixture import looks unused to a linter but is genuinely used by pytest, and the re-export states that honestly instead of muting the check.

The committed manifest is deliberately not regenerated as part of this Step. Other consolidations are still landing, and a manifest generated against a moving tree is stale before it is committed; it is regenerated once against a settled tree.
