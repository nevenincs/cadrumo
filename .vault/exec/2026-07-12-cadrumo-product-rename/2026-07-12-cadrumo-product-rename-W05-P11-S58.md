---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S58'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Retarget CI source paths and named product jobs

## Scope

- `dev/packaging/tests/test_ci_workflow.py` (implementation)
- `.github/workflows/ci.yml` (unchanged production evidence)

## Description

- Verify the production workflow retains Cadrumo-owned labels and source paths
  while invoking `aeat` as the sole human CLI.
- Replace the blanket `aeat` token ban with exact registry-command assertions.
- Reject former product distribution, Python import/module, install/package,
  and source-path form families, and reject any `cadrumo` human executable
  alias.
- Prove the classifier with parametrized allowed human-CLI/authority cases and
  prohibited import, install, package-selection, distribution, and source cases.

## Outcome

The primary CI workflow remains `Cadrumo CI`, with Cadrumo-owned job identity
and `src/cadrumo` source paths. Its two registry commands invoke the sole human
CLI exactly as `uv run --no-sync aeat ...`. The structural gate permits those
contractual executable uses while rejecting `cadrumo` in executable position
and former `aeat` product/package/source identities.

## Notes

Direct YAML parsing, Ruff formatting and lint, Ty, and twenty real workflow
structure cases passed. The production CI workflow required no edit. Justfile,
documentation, release runbooks, and other workflow files were excluded. This
record also cross-carries the authorized sanitizer's removal of stale scaffold
template comments; no other sanitizer path is included.

## Reopened (2026-07-13, bookkeeping audit)

This Step was reopened during the W06.P14.S76 residue audit. Reinspection found
that the production workflow already used `aeat` for both registry commands;
the stale record described superseded bytes. The remaining defect was the test's
contradictory blanket assertion that no `aeat` token could appear despite its
own exact `aeat` command requirements. The referent-aware structural gate now
closes that defect without weakening former-identity or dual-executable checks.

## Review remediation (2026-07-13)

The independent S58 audit found that the first referent-aware gate still used a
short literal list and therefore missed valid prohibited forms such as
`from aeat import ...`, `uv pip install aeat`, and
`uv run --package aeat ...`. The replacement gate classifies complete regex
families for Python imports/modules, distribution installation, uv package
selection, former distribution names, and former source paths. Exact `aeat`
human CLI invocations and AEAT authority prose remain explicitly accepted.

The follow-up review found two remaining boundary defects. The Python-module
family now covers dotted submodules such as `python -m aeat.cli`, and the
distribution-install family stops at shell command separators instead of
consuming a later allowed `aeat` CLI invocation or AEAT authority sentence.
Direct witnesses cover both rejected former-product forms and allowed chained
commands. All twenty-five structural cases, Ruff lint, Ruff format, and Ty pass.
