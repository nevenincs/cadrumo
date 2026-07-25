---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S262'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run namespace registry and non-vacuous production adoption suites and reject duplicate declarations across every production root

## Scope

- `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `src/cadrumo/application/tests/test_namespace_registry_adoption.py`

## Description

- Run both named suites under an explicit execution-marker selection covering both lanes.
- Confirm a non-zero collected count before reading the result line.
- Test the non-vacuity claim directly rather than inferring it from a green result, by instrumenting each gate's own discovery helpers and counting the subjects they actually find.
- Test the every-production-root claim by searching for namespace literals outside the roots each gate guards.

## Outcome

Verdict: SATISFIED on the invariant, with a recorded weakness in one of the two named gates.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py src/cadrumo/application/tests/test_namespace_registry_adoption.py`.

Collected 27, passed 27, failed 0, skipped 0. Exit line: `27 passed in 27.41s`, exit code 0. HEAD at run time was `1844ef2ea03314f47bfb0cdcfaac17d0fe08be26`. The serial and OS-keychain selections both collected nothing.

The storage-side gate carries the Step's claim and carries it honestly. Its discovery pass walks every production source in the package, resolves imported registry bindings as well as bare literals, and asserts a positive floor of five known namespaces before asserting that nothing discovered is unregistered. That floor is a real anti-vacuity assertion: if discovery stopped finding namespaces the gate would fail rather than pass empty. Sixty-six namespace rows are checked for owner prefix and authority segments, custody disposition, mirror policy, and duplicate rejection.

The application-side adoption gate does not carry it. Instrumenting its own helpers against the live tree shows it walks 879 guarded production files and finds zero namespace literal usages, then asserts that its offence list is empty. The assertion is trivially true and would remain true if the registry authority were removed. It also guards three roots rather than every production root. Both weaknesses are benign today and neither is a correctness failure: a direct search confirms no secure-object namespace literal survives in production outside those three roots, and the storage-side gate covers the whole package with a non-vacuous floor. The Step's invariant is therefore genuinely proven, but by one gate rather than the two it names.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. The vacuity finding was established by executing the gate's own helper functions against the live tree, not by semantic search.

The adoption gate's emptiness is a direct consequence of the campaign succeeding: the earlier Steps removed the duplicate literals it was written to catch. Its own docstring anticipates literals that no longer exist. Left as is it will pass forever regardless of what happens to the registry, so it is a candidate for either an anti-vacuity floor of its own or retirement in favour of the storage-side gate.
