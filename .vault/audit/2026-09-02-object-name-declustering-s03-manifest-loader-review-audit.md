---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:9881d06cfb61a5a88cd386c90c535690c6fa5bb36ef37da1e0f7a0d1b4f30aac'
related:
  - "[[2026-09-02-object-name-declustering-plan]]"
---

# `object-name-declustering` audit: `s03 manifest loader review`

## Scope

Reviewed `dev/quality/object_name_manifest.py` for `W01.P02.S03` against the
accepted research, repository reference, ADR, plan, and naming, path-safety,
fail-closed, architecture, and local-execution rules. The review covered strict
TOML loading, schema validation, disposition and lifecycle semantics, finding
and declaration binding, locator/path consistency, target claims, exact-byte
preconditions, generated-owner declarations, execution selection, and manifest
digesting. No implementation or test file was changed.

Ruff lint and formatting checks passed. The canonical `ty` checker passed for
the module, and importing the live module succeeded. Dedicated detector-teeth
tests remain correctly assigned to `W01.P02.S04`; the findings below are
contract defects visible in the implementation itself rather than missing test
coverage.

## Findings

### prohibited-disposition | high | `keep-distinct` remains a valid manifest disposition

`OperationDisposition` still includes `keep-distinct`, and
`ObjectNameRenameOperation._validate_operation_shape` accepts it as an
adjudication-only operation. The accepted ADR explicitly prohibits this
disposition because raw-zero completion requires every enforced finding to
disappear. Such a row therefore passes strict loading and live inventory
validation even though it cannot be valid reviewed intent for this lane.

### finding-operation-cardinality | high | One-operation-per-finding blocks atomic collision cleanup

`ObjectNameRenameManifest._require_unambiguous_operations` rejects every repeated
`finding_id`, requiring exactly one operation for a selected finding. A duplicate
finding can contain three or more qualified sites and require several distinct
rename operations while retaining one finding identity. The research explicitly
states that finding count is not operation count and that collision membership
creates hard graph edges. The current cardinality rule prevents one reviewed
component from carrying all necessary operations, forcing partial sequential
renames and stale finding identities instead of the accepted atomic batch.

### target-locator-binding | high | Proposed locators are not bound to target paths or binding identity

Validation checks only locator kind and, for module renames, compares the target
filename stem with the locator leaf. A symbol operation may therefore retain
`new_path` while naming an unrelated module in `new_locator` or changing its
`#binding` occurrence. A module operation may likewise name a different package
or binding occurrence, or target a non-Python path whose stem happens to match.
These contradictory records pass the manifest model and are not rejected by
live validation. The reviewed manifest is intended to be the unambiguous
authority consumed by graphing and transformation, so locator module, target
path, declaration kind, and binding occurrence must describe one canonical
target.

## Recommendations

Remove `keep-distinct` from the accepted disposition vocabulary and reject it at
the strict model boundary. Retain `merge-authority` only as the explicitly
non-executable adjudication governed by the accepted ADR.

Permit multiple operations to reference one finding when they claim distinct
old locators from that finding. Enforce one consistent disposition per finding
and retain unique operation IDs, old locators, target locators, target names,
and move paths.

Derive the expected module locator from each normalized target path and require
an exact match. For symbol renames, require the target locator's module and
binding occurrence to match the old declaration while changing only the symbol
leaf. For module renames, require a Python module path, the canonical module
qualified name derived from that path, and binding occurrence one. Add the
corresponding refusal cases in `W01.P02.S04`.

## Re-review resolution evidence

The reconciled implementation removes `keep-distinct` from
`OperationDisposition`; the live import exposes only `lexical-singular`,
`rename-distinct`, and non-executable `merge-authority`. This closes
`prohibited-disposition`.

Repeated `finding_id` values are now accepted when every row carries one shared
disposition. Independent uniqueness checks remain for operation IDs, old
locators, target locators, move sources, and move targets. Live validation still
requires every old locator to belong to the selected enforced finding, so
advisory findings remain rejected. This closes
`finding-operation-cardinality` without weakening unique source or target
claims.

Live target validation now derives the expected qualified locator by applying
`dataclasses.replace` to the selected source declaration with the proposed leaf
name and target path. This correctly binds symbol targets to their defining
module and original binding occurrence, and module targets to the qualified
module derived from the target path. The main ambiguity in
`target-locator-binding` is resolved.

### module-target-suffix | medium | Module targets may still leave the Python module domain

`_safe_source_path` constrains paths to `src/` or `dev/` but does not require a
`.py` suffix. The operation model accepts a reviewed module move from
`src/cadrumo/old.py` to `src/cadrumo/renamed.txt`, and the new canonical locator
derivation also accepts it because module-name derivation removes any suffix.
Such intent can pass target path/locator validation even though the destination
will no longer be enrolled as a Python module. The accepted manifest boundary
must refuse this destructive domain change before transformation.

Re-review checks passed: Ruff lint, Ruff formatting, canonical `ty` checking,
and live import. No critical or high finding remains. One medium finding remains
open; no low finding remains.

## Final resolution evidence

The module-operation model now refuses every `new_path` whose
`PurePosixPath.suffix` is not `.py`, and live inventory validation independently
requires both old and new module paths to be Python files. Re-running the exact
previous counterexample confirmed that `src/cadrumo/old.py` to
`src/cadrumo/renamed.txt` raises validation with the expected refusal. This
closes `module-target-suffix`.

Final checks passed: Ruff lint, Ruff formatting, canonical `ty` checking, live
import, and the focused non-Python-target refusal probe. No critical, high,
medium, or low finding remains open for `W01.P02.S03`.
