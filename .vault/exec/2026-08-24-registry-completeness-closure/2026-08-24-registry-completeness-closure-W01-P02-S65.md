---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:854fb236a6f89183f615fde1451e876a4a6cdb70607ec7ea26c6235d8d11c21e'
step_id: 'S65'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Add a hostile RegistryClosureAuthorities CLI context backed by eligible real protocol implementations, prove the shipped command ignores it, restore the exact former find_object authority branch for a mutation bite, and retain non-CLI loader injection

## Scope

- `dev/registry/conformance/tests/test_closure.py`
- `dev/registry/conformance/cli.py`
- `dev/registry/conformance/authorities.py`
- `dev/registry/conformance/closure.py`

## Description

- Add an exact `RegistryClosureAuthorities` Typer context whose bundled registry and protocol-complete source and filing ports are hostile tripwires.
- Assert the shipped `closure --check` command ignores that context, follows canonical live composition, remains release-ineligible, and calls neither supplied port.
- Restore the exact former `context.find_object(RegistryClosureAuthorities)` branch temporarily and run the hostile-context test as a mutation bite.
- Restore the shipped source byte-for-byte at the removed branch surface and retain the programmatic `load_registry_closure_report` injection ports.

## Outcome

The public command does not consume a context-supplied authority container. The intact hostile-context test passed with the canonical live ineligible result and no tripwire calls. Restoring the exact former branch caused the test to fail when `proof_for` raised `AssertionError`, proving that the test reaches and rejects the specific removed authority-selection bypass.

## Notes

The code-and-test surface evidence passed: `ruff check` and `git diff --check` scoped to `dev/registry/conformance/tests/test_closure.py`. That scoped diff deliberately excluded this execution record, the plan, and the feature index. The original whole-commit `git show --check 8afc6890b6` instead reported the trailing blank line in this record; S66 removes it and records the re-attestation. The focused hostile-context test passed in 36.43 seconds before the mutation. The restored former branch made it fail in 38.99 seconds with `hostile closure context invoked proof_for`; the production source was then restored and the CLI diff was empty. Exit 0 is correctly unattainable without a durably enrolled filing proof, so the mutation proof uses an observable forbidden invocation rather than fabricated success evidence.
