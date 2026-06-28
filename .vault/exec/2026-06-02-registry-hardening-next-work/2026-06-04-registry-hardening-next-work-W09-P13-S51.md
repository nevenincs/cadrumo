---
tags:
  - '#exec'
  - '#registry-hardening-next-work'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S51'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `registry-hardening-next-work` `W09.P13.S51` regression

Scope: add real-behavior regression coverage for the generic revision and
fragmentation contract gap identified by S50.

## Description

- Added a positive directory-mode `revisions/<id>.toml` loading regression.
- Added committed-corpus coverage for M036, M100, M200, and M303 through the
  generic source discovery path.
- Added a schema/loader contract regression that fails if repeatable
  `ModeloRevision` fields are not classified by the fragment compiler.

## Outcome

S51 completed. The generic loader contract now has non-vacuous coverage for
plain revision files, key committed fragment-directory modelos, and repeatable
revision field merge classification.

## Notes

No loader or schema semantics changed. The new tests import and exercise the
real registry loader and schema models directly.
