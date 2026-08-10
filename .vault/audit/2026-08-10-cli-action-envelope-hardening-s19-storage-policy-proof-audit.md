---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:8276ba07299aa403a6b2b3b78d05842ce6f906bacce812e90fbcb6df5162b2ba'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cli-action-envelope-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-action-envelope-hardening` audit: `S19 storage-policy exact scenario proof`

## Scope

Audited the final `W03.P05.S19` test implementation in `HEAD` in
`src/cadrumo/application/tests/test_storage_write_policy.py` against the
current storage-write-policy producer and the strict operator-action models.
The review covered all seven current policy classifications, the two refusing
routes, fixed condition/evidence/action literals, complete missing-binding
serialization including null source fields, allowed verdict absence,
conditionality, action-versus-no-recovery exclusivity, and the settings
environment identities. The focused owner suite, Ruff, and basedpyright passed.

The matrix keeps the expected refusal contracts independent of the producer:
it does not mirror route classification or verdict-building logic, uses no
mock, fake, stub, patch, monkeypatch, skip, or xfail mechanism, and does not
perform the clean-root recovery-and-retry journey reserved for `W03.P05.S20`.

## Findings

### production-derived-scenario-denominator | high | The seven-row matrix is not reconciled to live policy classifications

Status: open. The matrix contains seven handwritten `pytest.param` rows and
asserts their serialized `code` literals, while the production
`StorageWritePolicyCode` enum currently also has seven members. The test does
not derive a scenario key from that enum or compare the observed scenario-key
set with the production classification set; its only matrix use of
`StorageWritePolicyCode` is the two rendering branches after the full-payload
assertion. Adding a new policy classification and return branch without adding
a matrix row would therefore leave the focused suite green, despite S19's
requirement to prove every policy outcome.

## Recommendations

- For `production-derived-scenario-denominator`, make the scenario identity
  production-derived and fail when the matrix's scenario classifications differ
  from `StorageWritePolicyCode`. Retain the existing fixed expected verdict
  literals and deterministic settings fixtures; they provide the required
  independent contract evidence once the denominator cannot drift silently.
- Re-run the focused storage-write-policy suite, Ruff, and basedpyright after
  the denominator reconciliation. Keep clean-root recovery dispatch and retry
  out of this test module until `W03.P05.S20` owns that proof.
