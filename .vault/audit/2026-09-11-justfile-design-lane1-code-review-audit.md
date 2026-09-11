---
tags:
  - '#audit'
  - '#justfile-design'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:1c9666c403cf7c13ca0437e4c74833e284bc5a4c5cc6c42e32c6285512da1f92'
related:
  - "[[2026-09-11-justfile-design-plan]]"
  - "[[2026-09-11-justfile-design-adr]]"
  - "[[2026-09-11-justfile-design-research]]"
  - "[[2026-09-11-justfile-design-audit]]"
---

# `justfile-design` audit: `lane1 code review`

## Scope

The approved setup, doctor, check, fix, audit, and report surfaces were reviewed against the
justfile-design ADR, plan, research, and grounding audit. The review covered the owned
`dev/init`, `dev/env`, `dev/quality`, and `dev/audit` implementations, their focused tests,
and the corresponding justfile recipe membership, exit posture, and mutation boundaries.

## Findings

### scanner-payload-shape | MEDIUM | Malformed semgrep envelopes can escape advisory normalization

`dev/audit/security.py` rejected malformed JSON text, but a JSON list root or malformed result
record could raise while classifying the scanner output. That bypassed the typed unavailable
state and could make the advisory surface fail with an incidental traceback instead of the
documented advisory-broken status. A fail-closed parser correction is required before this
lane can close the scanner-normalization step.

Follow-up status: the parser now validates the JSON root, scan evidence, error list, result
records, object fields, and line types before constructing a result. Focused security and
advisory tests pass, so this finding is resolved for the lane.

### workflow-check-provisioning | MEDIUM | Workflow checks can provision actionlint when it is absent

`check-workflows` and `check-repository` invoke `dev/actionlint.py`, whose `ensure()` downloads
and writes a cached executable under `.venv/tools` when `actionlint` is not already on PATH.
That behavior is outside the owned Python surfaces, but it means the read-only check contract
is not guaranteed on a host without the executable. The current lane leaves this cross-owner
dependency for integration rather than editing the provisioner.

### corpus-generator-callers | LOW | Recipe rename still needs caller and guidance migration

The two committed corpus generators now use explicit `generate-corpus-*` names, while the
corpus extractor's module guidance still names the displaced `fix-corpus-*` command. No runtime
caller was found in the owned surface. The integration lane must update this guidance and prove
all tracked callers before retiring the old vocabulary.

## Recommendations

- Harden `classify_semgrep_output` to return unavailable for every invalid JSON envelope or
  finding record, and cover that contract with focused parser tests. Completed in the follow-up
  above.
- Give the actionlint owner a read-only check mode, or make the workflow check call an already
  installed executable while retaining download/provisioning only in setup.
- Migrate the corpus generator guidance and any tracked callers before the final alias-retirement
  gate.
