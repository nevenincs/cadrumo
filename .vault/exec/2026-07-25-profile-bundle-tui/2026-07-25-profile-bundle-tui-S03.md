---
tags:
  - '#exec'
  - '#profile-bundle-tui'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:3b7f2cc2c6f6d1291f774fb3aeb58384235961851583b527569f41b4803991e9'
step_id: 'S03'
related:
  - "[[2026-07-25-profile-bundle-tui-plan]]"
---

# Build the import FlowDefinition collecting the bundle path as a PATH and, only when --label was not given, an optional label as TEXT

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`

## Description

- Build the import definition in `build_import_flow_definition`, carrying the bundle path as a required PATH page.
- Append the label as a TEXT page only when `--label` was absent from the invocation, and mark it not required so an operator can accept the bundle's own display name by leaving it blank.
- Fold a blank label answer back to `None` in `import_request_from_state` so the downstream label resolution defaults to the bundled record's display name exactly as a non-interactive invocation does.
- Preserve an argv-supplied label verbatim, never re-asking for or overriding it.
- Declare checkpointing UNAVAILABLE in both modes, matching the export definition.

## Outcome

Landed in commit `c4545973f9`. This pass verified the step rather than re-implementing it.

Verified green in the same 13-test integration run. `test_scripted_import_run_collects_path_and_optional_label` drives the real flow engine through all three shapes in one proof: a path plus a typed label, a path plus a blank label folding to `None`, and a definition built without the label page whose argv label survives untouched. The line-mode frontend drive renders and submits the real import definition over the production questionary prompts.

The step's contract is also exercised end to end by the roundtrip proof, which drives flow-collected answers into the live CLI import verb against real encrypted storage and asserts the re-exported bundle is strictly equal to the original as a typed portable-export model, modulo only the documented non-content-addressable `exported_at` stamp and the recipient-local registration timestamps.

## Notes

None.
