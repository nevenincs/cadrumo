---
tags:
  - '#reference'
  - '#data-file-quality'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:4d3fcfdbd2a4949bd61898fd2e5f3e096f1ac5e193db62e4e1c16564216540dd'
related: []
---

# `data-file-quality` reference: `Just and CI shape for TOML and YAML quality`

This reference maps the existing Just, quality-suite, CI-contract, registry,
locale, dependency, and file-custody boundaries that govern repository-wide
TOML and YAML checks.

## Summary

The canonical implementation belongs in `dev/quality/` as one data-file driver.
The Justfile should remain a thin facade. Registry parsing and typed semantic
validation already belong to `dev/registry/` through `just check-registry`; a
generic textual formatter there would mix repository source quality with AEAT
authority validation.

`justfile:213-216` defines `check-format` specifically as Ruff's Python format
check. Preserve that contract and add a sibling `check-data-format` in the
static-check section. Enrol its identical primitive command in
`dev/quality/suite.py`, following the drift-protected recipe/aggregate pattern
asserted by `dev/quality/tests/test_suite_gate_table.py`. Data formatting does
not belong in `check-repository`, whose scope at `justfile:328-336` is identity,
generated API stubs, workflows, and CI contracts.

Mutation must remain separate and explicitly bounded. Add
`fix-data-format PATH` beside `fix-code PATH`; do not expose a default
repository-wide rewrite. This follows the ownership boundary documented at
`justfile:582-606`.

The existing `check-yaml` and `check-toml` entries in `prek.toml` are not an
authority to extend. `prek.toml:3-14` declares the configuration uninstalled
and manual, while `justfile:355-360` excludes `check-hooks` from aggregates.
Remove the duplicate generic hooks or make them delegate to the canonical
driver so path policy and diagnostics have one declaration site.

Both `.github/workflows/ci.yml` and `.github/workflows/ci-full.yml` currently
call `check-style` and `check-format` explicitly in their Lint step. Add the
public `check-data-format` recipe there while also enrolling it in
`check-code`; replacing the workflow step with `check-code` would broaden CI
to unrelated gates and is outside this feature. CI must call the recipe rather
than reimplement its tool commands, per `dev/ci_contract.py`.

Generic development dependencies belong in `[dependency-groups].dev` in
`pyproject.toml`. The existing `rtoml` declaration is intentionally in the
registry group for registry writers and rendering, so it is not evidence of a
whole-tree formatter.

Path policy must be explicit. Never scan or mutate
`src/cadrumo/_data/corpus/**`: `.gitattributes` declares those artefacts
byte-exact evidence. TOML checks should cover authored registry and repository
TOML while excluding caches, lock artefacts, generated output, and byte-exact
corpus. YAML checks should cover repository YAML, including CloudFormation
custom tags. Generic YAML mutation must refuse `src/cadrumo/locales/**` because
locale catalogue mutation is owned by the locale CLI; `check-locales` remains
the semantic catalogue gate.

The current manual syntax hooks are not green: `check-toml` rejects mixed
carriage returns in `dev/registry/pipeline/generated_tree_dispositions.toml`,
and `check-yaml` rejects CloudFormation `!Ref` in
`infra/docs-static-site.yaml`. A new blocking gate therefore needs tag-aware
YAML handling and a formatting sweep before CI enrolment.

Tests belong in `dev/quality/tests/` and should prove complete source-tree
discovery, corpus and generated exclusions, malformed TOML/YAML detection,
CloudFormation-tag support, format drift, read-only check behavior,
explicit-path repair boundaries, locale mutation refusal, and tool failure
propagation.
