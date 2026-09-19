---
tags:
  - '#audit'
  - '#registry-authoring-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:efef6daa344ccf4770a7962550f4ee2bd67e4ff74a40d1bbb18d85f6826e7c7c'
related: []
---

# `registry-authoring-boundary` audit: `Production/development registry-authoring boundary`

## Scope

## Findings

### stale-cli-reference-and-doc-contracts | high | Removed registry verbs remain in generated and authored documentation contracts

The live command graph no longer contains `aeat app registry manuals list`, but `dev/docs/tests/test_cli_tree.py::test_sociedades_manual_list_projects_coverage_help_and_identifier` still resolves that path and fails with `CliTreePathNotFoundError`. The focused command was `uv run --no-sync pytest -q -n0 src/cadrumo/entrypoints/cli/tests/test_repair_bootstrap_exempt.py src/cadrumo/entrypoints/cli/tests/test_root_placement_criterion.py dev/docs/tests/test_cli_tree.py dev/docs/tests/test_sequence_goldens.py dev/docs/sequences/tests/test_host_conditional_fact_masking.py`; it exited 1, with that failure. `docs/_static/cli-tree.json` still publishes the full retired `app registry` tree and `config repair integrity registry`; its owning generated artifact has not been refreshed. Authored sequence fixtures and help text also still direct operators to retired `app registry inspect`, `app registry citations`, and `config repair integrity registry`. This violates the live-tree documentation contract and makes released documentation describe commands that reject at runtime.

### stale-bootstrap-and-packaging-contracts | high | Retired verbs remain executable expectations in bootstrap and packaging gates

`src/cadrumo/entrypoints/cli/_bootstrap_exempt.py` still grants a prefix exemption to `app registry`, including every removed subtree member. The registration-resolve gate explicitly requires every exemption to name a registered verb, so `test_bootstrap_exempt_entries_resolve.py` will fail when collected. Separately, `dev/packaging/smoke_split_install.py` still executes `app registry verify`, and `dev/packaging/python_cohort.py` still selects `aeat app registry inspect`; the packaging workflow test still names `config repair integrity registry`. These are not historical prose: they are active gate and installed-wheel behavior definitions. The removal therefore has not completed its blast radius and the relevant packaging gates cannot pass as claimed.

### conformance-composer-still-shipped-under-src | high | Development conformance still depends on a production-package test module

`dev/registry/conformance/manager.py` imports `audit_bundled_registry_conformance`, `RegistryConformanceProfile`, and associated coverage types from `cadrumo.tests.registry_conformance` and `cadrumo.tests.registry_coverage`. The moved `integrity` command is development-only, but the report and coverage verbs still execute authoring/conformance composition from `src/cadrumo/tests/registry_conformance.py`. That directly contradicts the stated destination of `dev/registry/conformance` and leaves the major conformance implementation in the shipped package namespace. The implementation must be rehomed, with development tests adjusted to import the development module, before the boundary can be considered structurally complete.

### orphaned-topic-catalogue | medium | A production core registry-topic service has no remaining production consumer

`src/cadrumo/core/topics/catalogue.py` loads `registry/aeat/topics` and its package documentation still defines its CLI contract as `aeat app registry citations`. The only non-test consumer found by the repository search is `dev/docs/terminology_handbook/_enrolment.py`; the citation CLI adapter that previously rendered those records has been removed. This leaves a shipped core service that is functionally dead on the production path and whose contract names a retired user command. Rehome it to development documentation tooling or remove it after confirming no supported product reference surface needs it.

## Recommendations

- Regenerate the CLI-tree artifact through its owning generator, update or remove authored sequences and help fixtures, and replace the retired manual-list assertion with an assertion about an actually supported reference surface.
- Remove the `app registry` bootstrap exemption, then update packaging smoke/cohort contracts and their tests to exercise the development gate only where a development package workflow is intended.
- Move `registry_conformance.py` and `registry_coverage.py` implementation from `src/cadrumo/tests` into `dev/registry/conformance` (or a development-only subordinate package), preserving production authority consumption but eliminating the shipped authoring composer.
- Decide whether any product-facing reference access is still required. If not, remove the orphaned core topic catalogue and its error registrations; if yes, give it a justified non-registry product surface and update its documentation accordingly.
