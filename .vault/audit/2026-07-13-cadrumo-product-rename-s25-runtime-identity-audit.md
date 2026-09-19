---
tags:
  - '#audit'
  - '#cadrumo-product-rename-s25-runtime-identity'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:129d242c631d05406d62a4e2924cd6e643634c7aa851e39f20c54970a4a635ae'
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

**Remediation state: resolved by `e43a3bc4d0ba9f1d425e0d24a31c546eafae6d50`.**
The plan's exact S25 action and scope wording is unchanged, while its checkbox
is open again. A read-only Vaultspec plan query reports S25 as the sole open
Step in P05. The S25 record now distinguishes the landed runtime mechanics from
the still-failing live-help contract and says explicitly that formal review did
not accept the Step as complete.

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

## Remediation re-review

Verdict for the remediation state: **PASS**. This resolves the HIGH honesty
finding by restoring S25 to open status; it does not certify S25 implementation
or acceptance as complete.

Commit `e43a3bc4d0ba9f1d425e0d24a31c546eafae6d50` changes only the active plan
checkbox and the S25 execution record. It does not modify runtime code, tests,
locales, documentation, packaging, the binding ADR, or this audit. The execution
record preserves the original 20-test mechanics evidence, names the remaining
`Cadrumo` and `cadrumo <comando>` help defects, assigns their catalogue edits to
S62-S67, and requires a real installed-console assertion before S25 can close.
`git diff --check` passes. The plan's one annotation warning predates this
remediation and remains nonblocking.
