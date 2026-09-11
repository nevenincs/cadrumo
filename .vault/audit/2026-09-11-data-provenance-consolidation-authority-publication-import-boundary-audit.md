---
tags:
  - '#audit'
  - '#data-provenance-consolidation'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:e35d30642f8917584b95eda461f3731563cac32760337df11182107e9a1ff0e5'
related:
  - "[[2026-09-10-data-provenance-consolidation-adr]]"
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# `data-provenance-consolidation` audit: `authority-publication and import-boundary review`

## Scope

Reviewed the `W04.P08.S24` authority-publication fixture and the accompanying development-test import migration against the accepted caller-bounded artifact-catalog decision. The review covered provider-free isolated candidate compilation, the provider-present convenio projection, atomic refusal before artifact replacement, and the direct-import boundary between `dev` harnesses and the `cadrumo` package.

## Findings

### provider-present-convenio-refusal | medium | The new fallback has no isolated test proving a registered provider cannot omit the convenio fact

`compile_registry_tree` now creates an empty `ConvenioAuthority` only when the registration tuple is empty, while the provider-present branch still calls `convenio_authority_from_facts` and therefore refuses a missing `irnr.convenio.override` fact. The publication fixture proves the provider-free branch and the divergent record-design binding refusal, but it deliberately empties every provider registration and never exercises the opposite failure. The current bundled fact test proves a populated projection, not that an otherwise valid temporary publication candidate fails closed when a non-empty registration yields no convenio fact. This leaves the strictness of the new branch boundary without detector teeth.

### private-snapshot-internals-import | medium | The relocated `dev` support module directly imports a private runtime implementation module

The migration correctly removes relative traversal from `dev` into the `cadrumo` root, and the listed production-symbol imports now name their canonical package modules. However, `_referential_integrity_support` imports `_build_validated_snapshot` from `cadrumo.domain.calculations.registry._snapshot_internals`. That is a cross-package dependency on a private module, contrary to the import-boundary rule. The public `cadrumo.tests.registry_snapshot` harness only exposes the filing-grade helper, whereas these fixtures require an explicit lower grade; the missing public harness surface is the reason this private dependency remains.

### provider-present-convenio-matcher-lint | low | The new strict-provider detector currently fails Ruff's regular-expression rule

The new `pytest.raises` assertion passes a metacharacter-bearing literal to `match=`. Ruff reports `RUF043`, so the corrected detector is not yet green under the required focused lint gate. Use a raw string or an escaped literal while retaining the exact refusal assertion.

### provider-present-convenio-refusal | resolved | The enrolled-provider refusal now has isolated detector teeth

`test_provider_enrollment_requires_the_convenio_fact_before_publication` stages the same minimal candidate under the normal non-empty provider registrations, asserts the exact missing-fact refusal, and verifies the prior artifact bytes are preserved.

### private-snapshot-internals-import | resolved | The helper now uses a public test-support boundary

`cadrumo.tests.registry_snapshot.build_snapshot_for_validated_modelo` exposes the explicitly graded fixture operation without promoting the private runtime implementation. `_referential_integrity_support` consumes that test boundary.

### provider-present-convenio-matcher-lint | resolved | The refusal matcher is an explicit raw regular expression

The matcher now escapes the dotted fact identifier in a raw string. The focused seven-case publication suite, Ruff check, and formatting check pass.

## Recommendations

- For `provider-present-convenio-refusal`, add an isolated temporary-tree publication/compiler test with a non-empty provider registration that produces no `irnr.convenio.override` fact, and assert the exact refusal before the previous artifact can change. Keep the existing provider-free fixture as the separate supported-path proof.

- For `private-snapshot-internals-import`, expose the necessary explicitly graded snapshot construction through the existing `cadrumo.tests.registry_snapshot` harness (or another public test-support module), then make the `dev` support module consume that public boundary. Do not make `_snapshot_internals` a public production facade.

- For `provider-present-convenio-matcher-lint`, make the existing assertion's `match=` pattern explicitly raw or escaped, then rerun the focused Ruff check.

Resolution assessment, 2026-09-11: `provider-present-convenio-refusal` is resolved. The new temporary-tree publication test retains a prior artifact, leaves provider enrollment intact, and proves the exact missing-fact refusal; the seven-case authority-publication suite passes. `private-snapshot-internals-import` is resolved. `build_snapshot_for_validated_modelo` is a public test-harness boundary with an explicit grade, and the `dev` support module now consumes it rather than importing the private registry implementation. The independent matcher-lint finding remains open.

Resolution assessment, 2026-09-11: `provider-present-convenio-matcher-lint` is resolved by the escaped raw matcher; the focused Ruff gate passes.

- Fulfilled: the provider-present detector and public test-support boundary were added and verified by the focused authority-publication and referential-integrity collection checks.
