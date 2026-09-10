---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:47e324235d5724fc267c214324510fa0f76a73402774d49e2df4d90097b29e58'
step_id: 'S48'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [S | opus-medium] Give the predecessor key an explicit value meaning no predecessor exists, distinct from the key being absent. One modelo has three editions sharing a single validity date whose own declarations each assert they have no earlier sibling; without an explicit value it would be forced into a false sequence, and with the key merely absent it would be indistinguishable from a forgotten declaration. Proof: that modelo loads with all three editions declared parallel, and the forest rule accepts it without inventing an order.

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_revision_predecessor_declaration.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-exterior/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-importacion/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-union/revision.toml`
- `verify:` `uv run --no-sync aeat app registry verify` -> `pass` (HEAD `85ef41e47b`)
- `verify:` `pytest test_revision_predecessor_declaration.py test_modelo_369_registry.py test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable` -> `pass` (44)
- `verify:` 128 revisions dumped on one frozen package snapshot, HEAD schema and manifests vs changed -> 125 byte-identical, only the three 369 editions differ
- `verify:` `ruff check`, `ruff format --check`, `ty check` on changed Python -> `pass`

## Notes

The working tree was briefly unloadable while this Step ran. Other sessions saw the registry refuse 369's new `predecessor.none` tables with "predecessor must be the revision id of a sibling edition, got dict". That is the message of the schema before this change. The `schema.py` edits were saved before the manifest writes, but nobody confirmed that the new schema accepted the form across the whole corpus before the data landed. A process that had already imported the old schema could therefore read the new manifests. The order to follow from now on: change the schema, confirm every existing revision still loads with the new form accepted, and only then write data that uses it. Try data shapes in a scratch copy, not under `src/`.

The half of the proof that says the forest rule accepts 369 without inventing an order moves to S35 as a required proof, because no forest validator exists yet. For 369, S35 must accept three roots, each declaring `NoPredecessor`, sharing one `valid_from`, with no edges between them. It must treat that as a legal parallel set, not refuse it as "more than one root". It must also still refuse a second root that merely lacks the key. The ADR's forest paragraph currently says that all three 369 editions "declare the same predecessor". That does not match the corpus: 369 has no earlier edition for them to share. S35 or an ADR amendment has to settle the wording.

The references in a none declaration are pattern-typed and must not be empty, but they are not resolved against the legal and source catalogues at load time, the same as `family_dispositions`. The corpus test resolves 369's references.

In the full registry suite, 42 tests failed. One was this change (the TOML review line-length gate) and it is now fixed. The other 41 do not involve the predecessor, `schema.py` or modelo 369. They were not re-run against a control baseline.

The reviewer persona could not be launched. The orchestrating session reviewed the `schema.py` diff against the ADR: the three states are distinct types, the discriminator refuses every other shape, there is no reserved string, and the loader infers nothing. It then re-ran the predecessor and minimality tests (30 passed) and `registry verify` (exit 0).
