---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:145819eae81f010bd49dee37906d8e94538eab4b9df95a473cae53b2a0910e68'
step_id: 'S05'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Normalize completeness-manifest authoring to one shape

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/`
- `src/cadrumo/domain/calculations/registry/tests/test_completeness_manifest_authoring_shape.py`

## Description

- Relocate every manifest anchor to `completeness_manifest/0001-completeness_manifest.toml`.
- Keep large Modelo 100 continuation fragments in the same canonical directory without rewriting their content.
- Add a structural gate that compares canonical anchors with the loaded manifest-bearing revisions.
- Parse every semantic completeness-manifest fragment and reject any fragment outside its revision's canonical directory.

## Outcome

All 56 manifest-bearing revisions now expose the same canonical anchor. Fifty-seven tracked TOML blobs moved with zero content-hash differences. The focused shape gate passed, 42 directory-loader tests passed, and the real registry verifier remained green at 73 modelos and 94 revisions. Ruff, Ruff format, BasedPyright, scoped diff checking, and formal re-review passed. An independent novel-directory probe confirmed the gate detects a misplaced continuation.

## Notes

The first review found that a four-pattern legacy denylist did not exclude a new directory spelling. The final gate is property-based over parsed fragment content and carries no hard-coded manifest count or modelo allowlist.
