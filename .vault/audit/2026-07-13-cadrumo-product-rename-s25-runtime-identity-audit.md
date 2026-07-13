---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s25-runtime-identity'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename-s25-runtime-identity` audit: `S25 runtime CLI identity review`

## Scope

Commit `0589de6f0fab3e238998bd0d57f8be07c5903df4` was reviewed against the
binding executable ADR, the active plan, the S25 execution record, and every
changed path. The review exercised the real installed console, root and nested
usage errors, version and help fast paths, former-state refusal, startup
behavior, Windows launcher spelling, and unsupported launcher absence.

## Findings

### help-contract-closure | high | S25 is closed while its required help identity remains false

The checked S25 contract says the CLI's version and help product surfaces are
bound to `CADRUMO`, and the binding ADR requires product prose to say `CADRUMO`
while operator invocations use `aeat`. A real isolated `aeat --help` still
renders the heading `Cadrumo` and two `cadrumo <comando> --help` instructions.
The S25 record acknowledges those exact defects but nevertheless records the
Step as complete. The test change also removes the former title-case help-brand
assertion without replacing it with an assertion for `CADRUMO` or absence of a
human-command `cadrumo` token. Locale ownership correctly prevented an
out-of-scope catalogue edit, but it does not make the checked help acceptance
true. Closing S25 therefore reintroduces the plan-closure dishonesty that the
authority-lock remediation had just removed.

## Recommendations

Verdict: **FAIL**. The HIGH finding blocks the next lane from relying on S25 as
complete.

Keep S25 open until the locale-owned root-help strings are corrected through
S62-S67, or narrow the S25 plan contract and execution outcome explicitly to
runtime-generated root/prog/argv/usage/version identity while leaving all
catalogue-rendered help product copy open under S62-S67. In either case, add a
real installed-console assertion that the completed surface renders `CADRUMO`
and does not present `cadrumo` as a human command.

The underlying runtime mechanics are otherwise sound and nonblocking: root,
lazy registration, pinned program name, argv recognition, and short version
derive from `PRODUCT_IDENTITY`; `aeat.exe` is recognised case-insensitively;
root and nested parse errors render `aeat`; no CLI `python -m` entry exists;
and the `cadrumo` launcher is absent. Twenty real integration tests and scoped
Ruff checks passed. The changed tests contain no mocks, fakes, stubs, patches,
monkeypatches, skips, xfails, or mirrored business logic. Authority terminology,
locales, documentation, and packaging files were not mutated.
