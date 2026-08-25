---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:5ab9e390b4158114cbf3be434c84170d1d0a6fc4b45302cf9a1aa9ede607971b'
step_id: 'S172'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Hard-move the complete S126 producer-contract, registration contract type only, epoch, stamp, and inventory families from application/modelo/_workspace_producers.py into the sole public application/modelo/workspace_producers.py defining module, atomically migrate every exact production, test, documentation, tooling, annotation, registration, dynamic-target, and receipt consumer to direct imports, delete the private module plus every producer-contract or registration application.modelo package binding, __all__ entry, lazy name, and re-export, and gate the application.modelo namespace as inert in the same commit, replace epoch schema v1 with current-only schema v2 carrying the required native opaque comparison domain beside the unchanged generation, require exact domain equality before generation equality, currentness, or successor integer comparison, prove same-domain success and cross-domain refusal for equal, lower, and higher-looking generation integers plus strict schema-v1 and missing-domain refusal, regenerate the producer-contract and inventory digests, and reject the old schema without an alias, default synthesis, compatibility parser, shim, fallback, bridge, re-export, or private-path remnant, while leaving all eight concrete port realizations and field-manifest registration relocation exclusively to S167 and leaving physical same-root, distinct-root, root-switch, ABA, and cross-process domain derivation proofs to S173, S160-S167, and final conformance

## Scope

- `src/cadrumo/application/modelo/workspace_producers.py`
- `retired src/cadrumo/application/modelo/_workspace_producers.py`
- `src/cadrumo/application/modelo/__init__.py inert-namespace gate for producer-contract and registration bindings`
- `src/cadrumo/application/modelo/tests/test_workspace_producers.py`
- `every affected production/test/documentation/tooling/annotation/registration/dynamic-target/receipt consumer`
- `docs/api/cadrumo.application.modelo.rst`
- `retired docs/api/cadrumo.application.modelo._workspace_producers.rst`
- `and focused direct-import/epoch-v2/current-only/package-binding/zero-remnant tests`

## Description

- Promote the S126 producer contract, epoch, stamp, inventory, and structural port types into `application.modelo.workspace_producers`.
- Delete the private producer module and migrate the manifest and focused tests to direct public-module imports.
- Make the epoch schema current-only v2, require the opaque comparison domain, and reject cross-domain generation comparisons before ordinal evaluation.
- Regenerate contract and inventory digest inputs through the v2 static schema declaration.
- Replace the private API stub with the public stub and retain the inert `application.modelo` namespace.
- Confirm the semantic producer-authority discovery result with an exact source, documentation, tooling, and package-binding census.
- Obtain an independent code review with no triaged findings.

## Outcome

The producer-contract family has one public defining module. Its focused integration suite proves current-only v2 validation, same-domain currentness and successor behavior, cross-domain refusal for equal, lower, and higher-looking generations, digest reproduction, direct imports, inert package bindings, and the source/docs/dev zero-remnant fixed point.

## Verification

- `uv run --no-sync ruff check` passed for the S172 production and focused test modules.
- `uv run --no-sync pytest -q -o addopts='' -m integration` passed for the producer and field-manifest suites with 15 tests.
- `uv run --no-sync basedpyright` reported zero errors, warnings, and notes for the S172 Python surface.
- `uv run --no-sync python -m dev.docs.apidocs scaffold --check` reported a conformant API stub tree.
- Exact direct-import and private-path census found no active private producer import and one producer-family defining module.
- The path-scoped feature gate reran Ruff and the two focused integration modules successfully; the feature vault check is structurally clean for S172 and reports only unrelated existing feature-document and index warnings.
- The independent S172 review passed with no triaged findings.

## Notes

Implementation landed concurrently in `86943ad091` (`feat(modelo): cut workspace epochs to schema v2`) while this record was being finalized. That shared commit also includes the unrelated `src/cadrumo/core/tests/test_persisted_format_enrolment_binding.py`; this record and the canonical plan closure are deliberately committed separately rather than rewriting peer history. The shared-tree-wide `dev/tests/test_import_hygiene_gate.py` baseline gate currently reports 132 unrelated cross-package private-import sites against its hard-zero baseline. The S172 direct-import and package-binding census is clean; no unrelated remediation was absorbed. Native comparison-domain derivation, concrete port realization, and field-manifest registration remain deliberately deferred to their assigned steps.

